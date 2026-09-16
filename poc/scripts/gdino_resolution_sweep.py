"""GDINO 를 입력 해상도만 낮추면 얼마나 빨라지는가.

"경량화로 살릴 수 있나" 에 대한 답을 추정이 아니라 실측으로 낸다.
CPU 로만 잰다. 폰 목표 500ms → 데스크탑 CPU 상한 60ms.

    uv run python scripts/gdino_resolution_sweep.py
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoProcessor, GroundingDinoForObjectDetection

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.config import NEGATIVE_PROMPTS  # noqa: E402

GATE_MS = 60.0
SIZES = [800, 640, 512, 416, 320]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf-id", default="IDEA-Research/grounding-dino-tiny")
    ap.add_argument("--data", type=Path, default=Path("../data"))
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()

    img = Image.open(sorted((args.data / "images").glob("*.jpg"))[0]).convert("RGB")
    text = ". ".join(["eyeglasses"] + [n.lower() for n in NEGATIVE_PROMPTS]) + "."

    processor = AutoProcessor.from_pretrained(args.hf_id)
    model = GroundingDinoForObjectDetection.from_pretrained(args.hf_id).eval()
    # CPU 로 고정. GPU 수치는 폰과 무관하다.
    model.to("cpu")

    print(f"{args.hf_id}  (CPU)\n")
    print(f"{'입력':>6} {'데스크탑 CPU':>14} {'SD685 추정':>18} {'관문 대비':>10}")

    base = None
    for size in SIZES:
        # 짧은 변 기준 리사이즈. longest_edge 도 같이 올려 가로세로비를 유지한다.
        processor.image_processor.size = {"shortest_edge": size,
                                         "longest_edge": int(size * 1333 / 800)}
        inputs = processor(images=img, text=text, return_tensors="pt")

        with torch.no_grad():
            model(**inputs)  # warmup
            times = []
            for _ in range(args.runs):
                t0 = time.perf_counter()
                model(**inputs)
                times.append((time.perf_counter() - t0) * 1000)

        med = statistics.median(times)
        if base is None:
            base = med
        print(f"{size:>6} {med:>11.0f}ms {med * 8:>8.0f}~{med * 15:<7.0f}ms "
              f"{med / GATE_MS:>8.0f}배")

    print(f"\n관문 {GATE_MS:.0f}ms. 800 대비 배수는 위 표의 첫 줄과 비교한다.")
    print("해상도만으로 관문에 들어오지 않으면, 남은 레버(INT8 2~3배)를 곱해도")
    print("부족하다는 뜻이다. 그 다음은 증류·프루닝이고 그건 트레이닝이다.")


if __name__ == "__main__":
    main()
