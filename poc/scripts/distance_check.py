"""검출된 박스 크기로 촬영 거리를 역산한다.

기획서 10절은 안경 폭 ~14cm, 수평 화각 ~65° 를 전제로 거리별 픽셀 폭을
추정했다. 같은 기하로 거꾸로 풀면, 박스가 프레임에서 차지하는 비율로부터
촬영 거리를 추정할 수 있다.

    ratio = 14cm / (2 * d * tan(32.5deg))
    d     = 0.14 / (1.274 * ratio)   [m]

이게 중요한 이유: 사진이 전부 코앞에서 찍힌 것이라면 "17/17 검출" 은 실제
사용 거리(1~2m)에 대해 아무것도 말해주지 않는다.

    uv run python scripts/distance_check.py --run ../runs/0a
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

HFOV_DEG = 65.0
GLASSES_WIDTH_M = 0.14


def distance_from_ratio(ratio: float) -> float:
    if ratio <= 0:
        return float("nan")
    return GLASSES_WIDTH_M / (2.0 * math.tan(math.radians(HFOV_DEG / 2.0)) * ratio)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=Path("../runs/0a"))
    ap.add_argument("--data", type=Path, default=Path("../data"))
    ap.add_argument("--model", default="grounding-dino-tiny")
    ap.add_argument("--prompt", default="eyeglasses")
    args = ap.parse_args()

    df = pd.read_csv(args.run / "raw_detections.csv")
    df = df[(df["model"] == args.model) & (df["prompt_mode"] == args.prompt)
            & (df["is_positive"] == 1) & df["score"].notna()]

    no_glasses = set()
    p = args.data / "no_glasses.txt"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                no_glasses.add(Path(line).stem)

    rows = []
    for (src, stype), g in df.groupby(["source_id", "source_type"]):
        if src in no_glasses:
            continue
        best = g.loc[g["score"].idxmax()]
        # 프레임의 긴 변을 수평 화각 기준으로 본다 (세로 사진이면 회전한 것)
        frame_w = max(best["img_w"], best["img_h"])
        box_w = abs(best["x2"] - best["x1"])
        box_h = abs(best["y2"] - best["y1"])
        long_side = max(box_w, box_h)
        ratio = long_side / frame_w
        rows.append({
            "source_id": src,
            "type": stype,
            "score": round(float(best["score"]), 3),
            "box_long_px": round(long_side),
            "frame_long_px": int(frame_w),
            "frame_ratio": round(ratio, 4),
            "est_distance_m": round(distance_from_ratio(ratio), 2),
        })

    out = pd.DataFrame(rows).sort_values("frame_ratio", ascending=False)
    print(f"모델 {args.model} / 프롬프트 {args.prompt}\n")
    print(out.to_string(index=False))

    d = out["est_distance_m"]
    print(f"\n추정 거리  최소 {d.min():.2f}m  중앙값 {d.median():.2f}m  최대 {d.max():.2f}m")
    print(f"1m 이상에서 찍힌 것: {int((d >= 1.0).sum())}/{len(d)}")
    print(f"2m 이상에서 찍힌 것: {int((d >= 2.0).sum())}/{len(d)}")
    print("\n주의: 박스가 안경을 딱 맞게 감쌌다고 가정한 추정이다. 박스가 크게")
    print("      잡혔으면 거리가 실제보다 가깝게 나온다. 순위 비교용으로 본다.")


if __name__ == "__main__":
    main()
