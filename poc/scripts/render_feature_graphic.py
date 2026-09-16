"""Play 스토어 그래픽 이미지(1024×500) — 글자 없이 그림만.

돋보기 렌즈 중심을 이미지 정중앙에 두고, 렌즈에서 퍼지는 옅은 동심원("찾는 중")으로
가로로 긴 화면을 채운다. 모든 요소가 한 중심을 공유해서 좌우·상하 균형이 맞는다.
언어와 무관해서 한 장으로 모든 언어에 쓴다.

도형은 render_store_icon.py 와 같은 108 격자 좌표를 쓴다 (돋보기 렌즈 중심 52,52).

    uv run python scripts/render_feature_graphic.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "release" / "feature-graphic.png"

W, H = 1024, 500
SS = 4  # 4배로 그린 뒤 줄여 계단을 없앤다

BG = (255, 217, 90)
RING = (240, 190, 40)
INK = (43, 43, 48)
GLASS = (234, 246, 255)
LENS = (234, 246, 255)

# 돋보기 크기: 108 격자 1 단위 = K 픽셀. 렌즈(반지름 22) 가 화면 높이의 약 1/3.
K = 4.0 * SS
CX, CY = W * SS / 2, H * SS / 2  # 렌즈 중심 = 화면 중심


def P(x: float, y: float) -> tuple[float, float]:
    """108 격자 좌표 → 픽셀. 렌즈 중심 (52,52) 가 화면 중심에 온다."""
    return CX + (x - 52) * K, CY + (y - 52) * K


def quad(p0, c, p1, n=24):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t ** 2 * p1[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t ** 2 * p1[1])
            for t in (i / n for i in range(n + 1))]


def stroke(d, pts, width, color):
    px = [P(*p) for p in pts]
    w = width * K
    d.line(px, fill=color, width=round(w), joint="curve")
    for x, y in (px[0], px[-1]):
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=color)


def main() -> None:
    img = Image.new("RGB", (W * SS, H * SS), BG)
    d = ImageDraw.Draw(img, "RGBA")

    # 찾는 중 — 렌즈에서 퍼지는 동심원. 바깥으로 갈수록 옅게.
    for i, r in enumerate((170, 270, 370, 470)):
        rr = r * SS
        a = 150 - i * 32
        d.ellipse([CX - rr, CY - rr, CX + rr, CY + rr], outline=RING + (a,), width=7 * SS)

    # 손잡이
    stroke(d, [(68, 68), (79, 79)], 9, INK)

    # 돋보기
    r, sw = 22, 6
    d.ellipse([*P(52 - r - sw / 2, 52 - r - sw / 2), *P(52 + r + sw / 2, 52 + r + sw / 2)], fill=INK)
    d.ellipse([*P(52 - r + sw / 2, 52 - r + sw / 2), *P(52 + r - sw / 2, 52 + r - sw / 2)], fill=GLASS)

    # 안경 (앱 아이콘과 같은 모양, 0.47 배, 렌즈 가운데)
    s, tx, ty, lw = 0.47, -2, -1.5, 4

    def T(x, y):
        return (54 + (x - 54) * s + tx, 54.5 + (y - 54.5) * s + ty)

    for x0 in (27, 57):
        a, b = T(x0, 45.5), T(x0 + 24, 63.5)
        d.rounded_rectangle([*P(*a), *P(*b)], radius=8 * s * K, fill=LENS)
        h = lw * s / 2
        d.rounded_rectangle([*P(a[0] - h, a[1] - h), *P(b[0] + h, b[1] + h)],
                            radius=(8 * s + h) * K, outline=INK, width=round(lw * s * K))
    stroke(d, [T(*p) for p in quad((51, 51.5), (54, 47.5), (57, 51.5))], lw * s, INK)
    stroke(d, [T(27, 50), T(23, 48.5)], lw * s, INK)
    stroke(d, [T(81, 50), T(85, 48.5)], lw * s, INK)

    img.resize((W, H), Image.LANCZOS).save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
