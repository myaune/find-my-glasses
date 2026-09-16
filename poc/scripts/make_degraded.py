"""기존 사진을 열화시켜 찍지 않은 조건을 시뮬레이션한다.

촬영한 사진이 전부 근접(중앙값 0.30m)이라 기획서 10절이 말하는 실효 탐지
거리 1.5~2m 구간이 비어 있다. 새로 찍는 대신 있는 사진을 줄여서 채운다.

거리 시뮬레이션 방법
    안경이 프레임에서 차지하는 비율을 줄이면 멀리서 찍은 것과 같은
    "각크기" 가 된다. 이미지 내용을 s 배로 줄이고 원래 캔버스 크기까지
    반사 패딩으로 채운다.

**이것이 테스트하는 것과 하지 않는 것**
    O  안경이 N 픽셀만 차지할 때 검출되는가  ← 거리 문제의 핵심
    X  실제로 2m 떨어져 섰을 때의 장면
       (원근 변화, 새로운 가림, 초점 변화, 실제 배경의 방해물이 없다.
        패딩은 원본을 반사한 합성 영역이다.)

    uv run python scripts/make_degraded.py --data ../data --out ../runs/degraded/data
"""
from __future__ import annotations

import argparse
import math
import shutil
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

HFOV_DEG = 65.0
GLASSES_WIDTH_M = 0.14
# 실제 유스케이스는 "여기 어디쯤 뒀는데 안 보여서 못 찾는" 상황이다. 방 건너편
# 수색이 아니라 팔 길이~1.5m 근처를 훑는다. 1.0/1.5m 가 실사용 구간이고
# 2.0/3.0m 는 여유가 얼마나 있는지 보는 참고값이다.
TARGET_DISTANCES_M = [1.0, 1.5, 2.0, 3.0]


def ratio_for_distance(d_m: float) -> float:
    return GLASSES_WIDTH_M / (2.0 * math.tan(math.radians(HFOV_DEG / 2.0)) * d_m)


def shrink_pad(img: np.ndarray, s: float) -> np.ndarray:
    """내용을 s 배로 줄이고 원래 크기까지 반사 패딩."""
    h, w = img.shape[:2]
    nh, nw = max(1, int(round(h * s))), max(1, int(round(w * s)))
    small = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    top = (h - nh) // 2
    left = (w - nw) // 2
    return cv2.copyMakeBorder(small, top, h - nh - top, left, w - nw - left,
                              cv2.BORDER_REFLECT_101)


def low_light(img: np.ndarray, gain: float = 0.25, noise_sigma: float = 6.0) -> np.ndarray:
    out = img.astype(np.float32) * gain
    out += np.random.normal(0.0, noise_sigma, out.shape)
    return np.clip(out, 0, 255).astype(np.uint8)


def motion_blur(img: np.ndarray, length: int, angle_deg: float = 0.0) -> np.ndarray:
    length = max(3, length | 1)
    k = np.zeros((length, length), np.float32)
    k[length // 2, :] = 1.0
    M = cv2.getRotationMatrix2D((length / 2 - 0.5, length / 2 - 0.5), angle_deg, 1.0)
    k = cv2.warpAffine(k, M, (length, length))
    s = k.sum()
    if s > 0:
        k /= s
    return cv2.filter2D(img, -1, k)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("../data"))
    ap.add_argument("--run", type=Path, default=Path("../runs/0a"),
                    help="거리 추정에 쓸 기존 검출 결과")
    ap.add_argument("--out", type=Path, default=Path("../runs/degraded/data"))
    ap.add_argument("--model", default="grounding-dino-tiny")
    ap.add_argument("--prompt", default="eyeglasses")
    args = ap.parse_args()

    np.random.seed(0)

    # 기존 검출로 사진별 현재 거리를 추정한다.
    df = pd.read_csv(args.run / "raw_detections.csv")
    df = df[(df["model"] == args.model) & (df["prompt_mode"] == args.prompt)
            & (df["is_positive"] == 1) & df["score"].notna()
            & (df["source_type"] == "image")]
    base_ratio: dict[str, float] = {}
    for src, g in df.groupby("source_id"):
        best = g.loc[g["score"].idxmax()]
        frame_w = max(best["img_w"], best["img_h"])
        long_side = max(abs(best["x2"] - best["x1"]), abs(best["y2"] - best["y1"]))
        base_ratio[src] = long_side / frame_w

    no_glasses: set[str] = set()
    p = args.data / "no_glasses.txt"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                no_glasses.add(Path(line).stem)

    out_img = args.out / "images"
    if out_img.exists():
        shutil.rmtree(out_img)
    out_img.mkdir(parents=True, exist_ok=True)

    made_negative: list[str] = []
    n = 0
    srcs = sorted((args.data / "images").glob("*.jpg"))
    for path in srcs:
        stem = path.stem
        img = cv2.imread(str(path))
        if img is None:
            print(f"  건너뜀 (읽기 실패): {path.name}")
            continue

        variants: dict[str, np.ndarray] = {"orig": img}

        # 거리 — 안경이 있는 사진은 추정 비율로, 없는 사진은 고정 배율로
        for d in TARGET_DISTANCES_M:
            if stem in base_ratio:
                s = ratio_for_distance(d) / base_ratio[stem]
                if s >= 1.0:
                    continue  # 이미 그보다 멀다. 확대 시뮬레이션은 하지 않는다
            else:
                s = ratio_for_distance(d) / ratio_for_distance(0.3)
            variants[f"d{d:g}m".replace(".", "_")] = shrink_pad(img, s)

        # 저조도, 모션 블러 — 프레임 긴 변의 약 1% 길이로 흔든다
        variants["lowlight"] = low_light(img)
        variants["blur"] = motion_blur(img, int(max(img.shape[:2]) * 0.01))

        for cond, v in variants.items():
            name = f"{stem}__{cond}.jpg"
            cv2.imwrite(str(out_img / name), v, [cv2.IMWRITE_JPEG_QUALITY, 92])
            if stem in no_glasses:
                made_negative.append(name)
            n += 1
        print(f"  {stem}: {', '.join(variants)}")

    if made_negative:
        (args.out / "no_glasses.txt").write_text(
            "# make_degraded.py 가 생성. 원본이 안경 없는 사진인 변형들.\n"
            + "\n".join(sorted(made_negative)) + "\n",
            encoding="utf-8")

    print(f"\n{n}장 생성 → {out_img}")
    print(f"다음: uv run python -m bench.run_detect --data {args.out} "
          f"--out ../runs/degraded --models grounding-dino-tiny")


if __name__ == "__main__":
    main()
