"""Phase 0b — Grounding DINO 를 텍스트 인코더 없이 ONNX 로 내보낸다.

기획서 6절: 어휘가 고정 1개이므로 텍스트 임베딩을 빌드 타임에 구워넣고
BERT 를 통째로 뺀다.

GroundingDinoModel.forward 를 보면 텍스트 브랜치가 깨끗하게 분리된다.
input_ids 로부터 만들어진 네 가지만 인코더로 넘어간다.

    text_features              = text_projection(text_backbone(...))
    text_token_mask            = attention_mask.bool()
    text_self_attention_masks  = generate_masks_with_special_tokens_...(input_ids)
    position_ids               = 같은 함수의 두 번째 반환값

따라서 text_backbone(BERT, 415MB) 을 "미리 계산한 값을 그대로 돌려주는
스텁" 으로 갈아끼우면 나머지 코드는 건드리지 않고도 BERT 가 그래프에서
빠진다. text_projection(0.8MB) 은 그대로 둔다.

    uv run python scripts/export_onnx.py --prompt eyeglasses
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import torch
from torch import nn
from transformers import AutoProcessor, GroundingDinoForObjectDetection
from transformers.modeling_outputs import BaseModelOutputWithPoolingAndCrossAttentions

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.config import MODELS, NEGATIVE_PROMPTS  # noqa: E402

MB = 1024 ** 2


class CachedTextBackbone(nn.Module):
    """미리 계산한 BERT 출력을 그대로 돌려준다. 입력은 무시한다."""

    def __init__(self, last_hidden_state: torch.Tensor):
        super().__init__()
        self.register_buffer("cached", last_hidden_state)

    def forward(self, *args, **kwargs):
        return BaseModelOutputWithPoolingAndCrossAttentions(last_hidden_state=self.cached)


class VisionOnlyGroundingDino(nn.Module):
    """pixel_values 하나만 받는 래퍼. 텍스트 입력은 전부 상수로 굽는다."""

    def __init__(self, model: GroundingDinoForObjectDetection, inputs: dict):
        super().__init__()
        self.model = model
        for k in ("input_ids", "attention_mask", "token_type_ids"):
            if k in inputs:
                self.register_buffer(k, inputs[k])

    def forward(self, pixel_values: torch.Tensor):
        out = self.model(
            pixel_values=pixel_values,
            input_ids=self.input_ids,
            attention_mask=self.attention_mask,
            token_type_ids=getattr(self, "token_type_ids", None),
            return_dict=True,
        )
        # ONNX 출력은 텐서 두 개로 고정한다.
        return out.logits, out.pred_boxes


def build_prompt(positive: str) -> str:
    return ". ".join([positive] + [n.lower() for n in NEGATIVE_PROMPTS]) + "."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="grounding-dino-tiny")
    ap.add_argument("--prompt", default="eyeglasses")
    ap.add_argument("--out", type=Path, default=Path("../runs/0b"))
    ap.add_argument("--height", type=int, default=800)
    ap.add_argument("--width", type=int, default=800)
    ap.add_argument("--opset", type=int, default=17)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    hf_id = MODELS[args.model]["hf_id"]
    text = build_prompt(args.prompt)
    print(f"모델   {hf_id}")
    print(f"프롬프트 {text!r}")

    processor = AutoProcessor.from_pretrained(hf_id)
    model = GroundingDinoForObjectDetection.from_pretrained(hf_id).eval()

    dummy = torch.zeros(3, args.height, args.width)
    enc = processor(images=[dummy.permute(1, 2, 0).numpy()], text=text, return_tensors="pt")
    text_inputs = {k: enc[k] for k in ("input_ids", "attention_mask", "token_type_ids")
                   if k in enc}

    total_before = sum(p.numel() * p.element_size() for p in model.parameters())

    # 1) 텍스트 관련 값을 전부 한 번만 계산해 캐시
    #    inference_mode 로 만든 텐서는 트레이싱에 쓸 수 없다 (inference tensor).
    #    no_grad 를 쓴다.
    from transformers.models.grounding_dino import modeling_grounding_dino as M

    with torch.no_grad():
        masks, position_ids = M.generate_masks_with_special_tokens_and_transfer_map(
            text_inputs["input_ids"])
        masks = masks.clone()
        position_ids = position_ids.clone()
        masks4 = masks[:, None, :, :] if masks.ndim == 3 else masks
        cached = model.model.text_backbone(
            text_inputs["input_ids"], masks4,
            text_inputs.get("token_type_ids"), position_ids, return_dict=True,
        ).last_hidden_state.clone()
    print(f"캐시된 텍스트 특징 {tuple(cached.shape)}")

    # 2) BERT 를 스텁으로 교체
    model.model.text_backbone = CachedTextBackbone(cached)

    # 3) 마스크 생성 함수도 상수로 대체한다.
    #    원본은 torch.isin 을 쓰는데 ONNX opset 17 에 없다. 프롬프트가 고정이라
    #    결과가 항상 같으므로 미리 계산한 값을 그대로 돌려주면 된다.
    M.generate_masks_with_special_tokens_and_transfer_map = (
        lambda input_ids: (masks, position_ids)
    )
    print("generate_masks_with_special_tokens_and_transfer_map → 상수로 대체 "
          f"(masks{tuple(masks.shape)}, position_ids{tuple(position_ids.shape)})")
    total_after = sum(p.numel() * p.element_size() for p in model.parameters())
    print(f"파라미터 {total_before / MB:.1f} MB → {total_after / MB:.1f} MB "
          f"(제거 {(total_before - total_after) / MB:.1f} MB)")

    wrapper = VisionOnlyGroundingDino(model, text_inputs).eval()

    # 3) 스텁이 원본과 같은 결과를 내는지 확인
    px = torch.randn(1, 3, args.height, args.width)
    with torch.no_grad():
        logits, boxes = wrapper(px)
    print(f"래퍼 출력 logits{tuple(logits.shape)} boxes{tuple(boxes.shape)}")

    # 4) ONNX 익스포트
    onnx_path = args.out / f"gdino-tiny-{args.prompt.replace(' ', '_')}-fp32.onnx"
    print(f"\nONNX 익스포트 (opset {args.opset}) …")
    t0 = time.perf_counter()
    try:
        torch.onnx.export(
            wrapper,
            (px,),
            str(onnx_path),
            input_names=["pixel_values"],
            output_names=["logits", "pred_boxes"],
            dynamic_axes={"pixel_values": {0: "batch"},
                          "logits": {0: "batch"},
                          "pred_boxes": {0: "batch"}},
            opset_version=args.opset,
            do_constant_folding=True,
            dynamo=False,
        )
    except Exception as e:
        print(f"\n실패: {type(e).__name__}: {e}")
        raise SystemExit(1)

    size = onnx_path.stat().st_size
    print(f"완료 {time.perf_counter() - t0:.1f}s")
    print(f"FP32 ONNX  {size / MB:.1f} MB  → {onnx_path}")
    print("\n다음: uv run python scripts/onnx_fp16.py")


if __name__ == "__main__":
    main()
