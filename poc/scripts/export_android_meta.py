"""Android 앱이 필요로 하는 후처리 메타데이터를 JSON 으로 내보낸다.

ONNX 모델은 logits (1, 900, 256) 을 낸다. 256 은 텍스트 토큰 자리다.
어떤 토큰이 "eyeglasses" 이고 어떤 게 네거티브 어휘인지 알아야 점수를
클래스별로 모을 수 있다. 프롬프트가 고정이므로 이 대응표도 고정이다.

클래스 c 에 대한 쿼리 점수 = max over (c 의 토큰 자리) sigmoid(logit)
검출 = 클래스별 점수의 argmax. 그게 eyeglasses 면 양성.

    uv run python scripts/export_android_meta.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from transformers import AutoProcessor

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.config import NEGATIVE_PROMPTS  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf-id", default="IDEA-Research/grounding-dino-tiny")
    ap.add_argument("--positive", default="eyeglasses")
    ap.add_argument("--size", type=int, default=800)
    ap.add_argument("--out", type=Path, default=Path("../runs/0b/android_meta.json"))
    args = ap.parse_args()

    processor = AutoProcessor.from_pretrained(args.hf_id)
    tok = processor.tokenizer

    classes = [args.positive] + [n.lower() for n in NEGATIVE_PROMPTS]
    text = ". ".join(classes) + "."
    enc = tok(text, return_tensors="np")
    ids = enc["input_ids"][0].tolist()
    toks = tok.convert_ids_to_tokens(ids)

    dot_id = tok.convert_tokens_to_ids(".")
    sep_id = tok.sep_token_id
    cls_id = tok.cls_token_id

    # '.' 을 구분자로 클래스별 토큰 구간을 자른다.
    spans = []
    start = None
    idx = 0
    for i, tid in enumerate(ids):
        if tid in (cls_id, sep_id):
            continue
        if tid == dot_id:
            if start is not None:
                spans.append({
                    "name": classes[idx],
                    "start": start,
                    "end": i,  # exclusive
                    "tokens": toks[start:i],
                })
                idx += 1
                start = None
            continue
        if start is None:
            start = i

    if idx != len(classes):
        raise SystemExit(f"클래스 {len(classes)}개인데 구간 {idx}개만 찾았습니다: {spans}")

    ip = processor.image_processor
    meta = {
        "hf_id": args.hf_id,
        "prompt": text,
        "input_ids": ids,
        "tokens": toks,
        "max_text_len": 256,
        "num_queries": 900,
        "positive_class": args.positive,
        "classes": spans,
        "input": {
            "size": args.size,
            "layout": "NCHW",
            "rgb": True,
            "rescale": 1.0 / 255.0,
            "mean": list(ip.image_mean),
            "std": list(ip.image_std),
            "letterbox": "긴 변 기준 축소 후 가운데 배치, 남는 곳 0 으로 채움",
        },
        "recommended_threshold": 0.40,
        "note": (
            "클래스 점수 = max over 해당 구간 토큰 sigmoid(logit). "
            "검출 = 클래스별 점수의 argmax 가 positive_class 인 쿼리. "
            "pred_boxes 는 정규화 cxcywh (letterbox 정사각 기준)."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"프롬프트: {text}")
    print(f"토큰 {len(ids)}개\n")
    for s in spans:
        print(f"  [{s['start']:2d}:{s['end']:2d}]  {s['name']:16s} {s['tokens']}")
    print(f"\n→ {args.out}")


if __name__ == "__main__":
    main()
