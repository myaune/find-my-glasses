"""Play 스토어 그래픽 이미지(1024×500) — 글자·장식 없이 앱 아이콘 그림만, 정중앙에.
언어와 무관해서 한 장으로 모든 언어에 쓴다.

도형은 render_store_icon.py 와 같은 108 격자 좌표를 쓴다 (렌즈 중심 52,52, 손잡이 길이는 render_store_icon.geometry()).

    uv run python scripts/render_feature_graphic.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from render_store_icon import CX as LX, CY as LY, ICON_C, HANDLE_W, R_LENS, SW_LENS, geometry

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "release" / "feature-graphic.png"

W, H = 1024, 500
SS = 4  # 4배로 그린 뒤 줄여 계단을 없앤다

BG = (255, 217, 90)
INK = (43, 43, 48)
GLASS = (234, 246, 255)
LENS = (234, 246, 255)

# 돋보기 크기: 108 격자 1 단위 = K 픽셀. 렌즈(반지름 22) 가 화면 높이의 약 1/3.
K = 4.0 * SS
CX, CY = W * SS / 2, H * SS / 2


def P(x: float, y: float) -> tuple[float, float]:
    """108 격자 좌표 → 픽셀. 아이콘 가운데(= 기준 둥근 네모 중심)가 화면 중심에 온다."""
    return CX + (x - ICON_C) * K, CY + (y - ICON_C) * K


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

    # 손잡이
    g = geometry()
    stroke(d, [g["handle_start"], g["handle_end"]], HANDLE_W, INK)

    # 돋보기
    r, sw = R_LENS, SW_LENS
    d.ellipse([*P(LX - r - sw / 2, LY - r - sw / 2), *P(LX + r + sw / 2, LY + r + sw / 2)], fill=INK)
    d.ellipse([*P(LX - r + sw / 2, LY - r + sw / 2), *P(LX + r - sw / 2, LY + r - sw / 2)], fill=GLASS)

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
