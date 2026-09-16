"""Play 스토어용 512×512 아이콘 PNG 를 그린다.

앱 아이콘(android res/drawable/ic_launcher_*.xml)과 같은 도형을 같은 좌표(108 격자)로
그린다. 벡터를 바꾸면 여기도 같이 바꾼다. 4배로 그린 뒤 줄여 계단을 없앤다.

    uv run python scripts/render_store_icon.py
    uv run python scripts/render_store_icon.py --size 1024 --out ../ios/FindGlasses/Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512
SS = 4
# 런처는 108 격자 중 가운데만 보여주므로 스토어 아이콘은 가운데를 키워 채운다
ZOOM = 1.4
K = SIZE * SS / 108 * ZOOM  # 108 격자 → 픽셀

BG = "#FFD95A"
INK = "#2B2B30"
GLASS = "#EAF6FF"
LENS = (234, 246, 255, 230)
WHITE = "#FFFFFF"


def P(x: float, y: float) -> tuple[float, float]:
    # 108 격자의 (54,54) 를 이미지 가운데로
    c = SIZE * SS / 2
    return c + (x - 54) * K, c + (y - 54) * K


def quad(p0, c, p1, n=24):
    return [
        ((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t ** 2 * p1[0],
         (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t ** 2 * p1[1])
        for t in (i / n for i in range(n + 1))
    ]


def stroke(d: ImageDraw.ImageDraw, pts, width: float, color):
    px = [P(*p) for p in pts]
    w = width * K
    d.line(px, fill=color, width=round(w), joint="curve")
    for x, y in (px[0], px[-1]):  # 둥근 끝
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=color)


def main() -> None:
    global SIZE, K
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    SIZE = args.size
    K = SIZE * SS / 108 * ZOOM

    img = Image.new("RGBA", (SIZE * SS, SIZE * SS), BG)
    d = ImageDraw.Draw(img, "RGBA")

    # 손잡이
    stroke(d, [(68, 68), (79, 79)], 9, INK)

    # 돋보기 — 손잡이까지 합쳐 눈으로 가운데 오게 렌즈 중심 (52,52), 반지름 22, 테 굵기 6
    cx, cy, r, sw = 52, 52, 22, 6
    d.ellipse([*P(cx - r - sw / 2, cy - r - sw / 2), *P(cx + r + sw / 2, cy + r + sw / 2)], fill=INK)
    d.ellipse([*P(cx - r + sw / 2, cy - r + sw / 2), *P(cx + r - sw / 2, cy + r - sw / 2)], fill=GLASS)

    # 안경 — 원래 좌표를 (54,54.5) 기준 0.47 배 후 (-2,-1.5) 이동 → 렌즈 가운데
    s, tx, ty = 0.47, -2, -1.5
    lw = 4  # 원래 좌표계 기준 테 굵기

    def T(x, y):
        return (54 + (x - 54) * s + tx, 54.5 + (y - 54.5) * s + ty)

    for x0 in (27, 57):
        a, b = T(x0, 45.5), T(x0 + 24, 63.5)
        d.rounded_rectangle([*P(*a), *P(*b)], radius=8 * s * K, fill=LENS)
        # PIL 은 테두리를 안쪽으로 그린다. 안드로이드처럼 선 중심이 도형 경계에 오게 넓힌다
        h = lw * s / 2
        outer = [*P(a[0] - h, a[1] - h), *P(b[0] + h, b[1] + h)]
        d.rounded_rectangle(outer, radius=(8 * s + h) * K, outline=INK, width=round(lw * s * K))
    stroke(d, [T(*p) for p in quad((51, 51.5), (54, 47.5), (57, 51.5))], lw * s, INK)
    stroke(d, [T(27, 50), T(23, 48.5)], lw * s, INK)
    stroke(d, [T(81, 50), T(85, 48.5)], lw * s, INK)

    out = args.out or Path(__file__).resolve().parents[2] / "docs" / "release" / "icon-512.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.resize((SIZE, SIZE), Image.LANCZOS).convert("RGB").save(out)
    print(out)


if __name__ == "__main__":
    main()
