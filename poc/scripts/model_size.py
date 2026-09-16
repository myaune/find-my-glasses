"""모델 크기 측정 — 기획서 5절 "최종 크기 ≤ 100MB" 제약 확인.

기획서 6절은 어휘가 고정 1개이므로 텍스트 인코더를 빌드 타임에 제거하고
텍스트 임베딩을 구워넣는 것을 전제한다. 그래서 전체 크기가 아니라
"텍스트 인코더를 뺀 비전 브랜치" 크기가 실제 제약 대상이다.

여기서 재는 것은 파라미터 바이트 수다. 실제 ONNX 파일에는 그래프·상수가
더 붙으므로 하한선으로 봐야 한다.

    uv run python scripts/model_size.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.config import MODELS  # noqa: E402

MB = 1024 ** 2

# 각 모델에서 "텍스트 인코더"에 해당하는 최상위 서브모듈 경로.
TEXT_BRANCH = {
    "grounding-dino-tiny": ("model.text_backbone", "text_backbone", "text_projection"),
    "owlv2-base": ("owlv2.text_model", "owlv2.text_projection"),
}


def param_bytes(module) -> int:
    return sum(p.numel() * p.element_size() for p in module.parameters())


def walk_top(model, depth: int = 2):
    """최상위 서브모듈별 파라미터 크기."""
    rows = []
    for name, mod in model.named_modules():
        if not name:
            continue
        if name.count(".") >= depth:
            continue
        b = param_bytes(mod)
        if b > 0:
            rows.append((name, b))
    return rows


def main() -> None:
    for key in ("grounding-dino-tiny", "owlv2-base"):
        spec = MODELS[key]
        print(f"\n{'=' * 70}\n{key}  ({spec['hf_id']})  {spec['license']}\n{'=' * 70}")

        if spec["kind"] == "gdino":
            from transformers import GroundingDinoForObjectDetection as Cls
        else:
            from transformers import Owlv2ForObjectDetection as Cls
        model = Cls.from_pretrained(spec["hf_id"]).eval()

        total = param_bytes(model)
        print(f"전체          fp32 {total / MB:8.1f} MB   fp16 {total / MB / 2:8.1f} MB")

        # 텍스트 브랜치 식별
        text_bytes = 0
        found = []
        for path in TEXT_BRANCH[key]:
            mod = model
            try:
                for part in path.split("."):
                    mod = getattr(mod, part)
            except AttributeError:
                continue
            if isinstance(mod, torch.nn.Module):
                b = param_bytes(mod)
            elif isinstance(mod, torch.nn.Parameter):
                b = mod.numel() * mod.element_size()
            else:
                continue
            text_bytes += b
            found.append((path, b))

        if not found:
            print("  !! 텍스트 브랜치를 못 찾았습니다. 아래 서브모듈 목록 확인 필요")
        for path, b in found:
            print(f"  텍스트 제외분  {path:32s} {b / MB:8.1f} MB")

        rest = total - text_bytes
        print(f"\n비전 브랜치만  fp32 {rest / MB:8.1f} MB   fp16 {rest / MB / 2:8.1f} MB"
              f"   int8 {rest / MB / 4:8.1f} MB")
        print(f"목표 100MB 대비 (fp16): {'통과' if rest / MB / 2 <= 100 else '초과'}")

        print("\n  -- 최상위 서브모듈 --")
        for name, b in sorted(walk_top(model), key=lambda x: -x[1])[:12]:
            print(f"     {name:44s} {b / MB:8.1f} MB")

        del model

    print("\n주의: 파라미터 바이트만 센 값이다. 실제 ONNX 파일은 그래프·상수가")
    print("      더 붙으므로 이 숫자는 하한선이다.")


if __name__ == "__main__":
    main()
