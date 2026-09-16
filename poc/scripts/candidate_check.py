"""후보 하나를 빠르게 판정한다 — 속도와 검출률을 한 번에.

run_detect 는 프롬프트 4종을 프레임마다 돌려서 YOLO-World 의 set_classes
(CLIP 텍스트 인코딩)가 매 프레임 재실행된다. 그러면 느리고, 측정된 레이턴시도
오염된다. 여기서는 어휘를 한 번만 설정하고 사진을 한 번씩만 돌린다.

    uv run python scripts/candidate_check.py --weights yolov8l-worldv2.pt
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.config import NEGATIVE_PROMPTS  # noqa: E402

GATE_MS = 60.0


def load_no_glasses(data_dir: Path) -> set[str]:
    p = data_dir / "no_glasses.txt"
    if not p.exists():
        return set()
    out = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(Path(line).stem)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="yolov8s-worldv2.pt")
    ap.add_argument("--prompt", default="a pair of eyeglasses")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--data", type=Path, default=Path("../data"))
    args = ap.parse_args()

    from ultralytics import YOLOWorld

    classes = [args.prompt] + [n.lower() for n in NEGATIVE_PROMPTS]
    model = YOLOWorld(args.weights)
    model.set_classes(classes)          # 한 번만
    model.to("cpu")

    n_params = sum(p.numel() for p in model.model.parameters())
    no_glasses = load_no_glasses(args.data)
    files = sorted((args.data / "images").glob("*.jpg"))

    print(f"{args.weights}  imgsz {args.imgsz}  프롬프트 {args.prompt!r}")
    print(f"파라미터 {n_params / 1e6:.1f}M  (fp16 ≈ {n_params * 2 / 1024**2:.0f}MB)\n")

    pos_scores: list[float] = []
    neg_scores: list[float] = []
    times: list[float] = []

    for f in files:
        img = np.asarray(Image.open(f).convert("RGB"))
        t0 = time.perf_counter()
        res = model.predict(img, imgsz=args.imgsz, conf=0.01,
                            device="cpu", verbose=False)[0]
        times.append((time.perf_counter() - t0) * 1000)

        best = 0.0
        for b in res.boxes:
            if int(b.cls.item()) == 0:      # 0 = 찾는 대상
                best = max(best, float(b.conf.item()))
        (neg_scores if f.stem in no_glasses else pos_scores).append(best)
        mark = " (안경 없음)" if f.stem in no_glasses else ""
        print(f"  {f.stem}  {best:.3f}{mark}")

    med = statistics.median(times[1:]) if len(times) > 1 else times[0]
    lo, hi = float(np.min(pos_scores)), float(np.max(neg_scores or [0.0]))

    print(f"\n레이턴시   데스크탑 CPU 중앙값 {med:.0f}ms  → SD685 추정 "
          f"{med * 8:.0f}~{med * 15:.0f}ms")
    print(f"관문 {GATE_MS:.0f}ms → {'통과' if med <= GATE_MS else f'탈락 ({med / GATE_MS:.1f}배)'}")

    print("\n검출률 (안경 있는 사진 %d장)" % len(pos_scores))
    for t in (0.05, 0.10, 0.20, 0.25, 0.30, 0.40):
        n = sum(1 for s in pos_scores if s >= t)
        fp = sum(1 for s in neg_scores if s >= t)
        print(f"  임계 {t:.2f}  {n}/{len(pos_scores)}  (오탐 {fp}/{len(neg_scores)})")

    print(f"\n분리도  안경 있음 최저 {lo:.3f} / 없음 최고 {hi:.3f}  간격 {lo - hi:+.3f}")


if __name__ == "__main__":
    main()
