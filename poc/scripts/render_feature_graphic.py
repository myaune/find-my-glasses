"""Play 스토어 그래픽 이미지(1024×500)를 그린다 — 아이콘 + 앱 이름 + 한 줄 문구.

아이콘은 render_store_icon.py 로 만든 512px 이미지를 그대로 쓴다. 배경색이 같아서
경계 없이 붙는다. 글꼴은 Noto Sans KR (SIL Open Font License, 상업 이용 가능).

    uv run python scripts/render_store_icon.py
    uv run python scripts/render_feature_graphic.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "release"
ICON = OUT / "icon-512.png"
FONT = Path("C:/Windows/Fonts/NotoSansKR-VF.ttf")

W, H = 1024, 500
BG = "#FFD95A"
INK = (43, 43, 48)
SUB = (43, 43, 48, 200)

VARIANTS = {
    "ko": ("내 안경 찾기", "폰 카메라가 안경을 찾아드려요"),
    "en": ("Find My Glasses", "Your phone camera finds them"),
}


def font(size: int, weight: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT), size)
    try:
        f.set_variation_by_axes([weight])
    except OSError:
        pass  # 가변 글꼴 축을 못 쓰면 기본 굵기
    return f


def fit(draw: ImageDraw.ImageDraw, text: str, size: int, weight: int, max_w: int) -> ImageFont.FreeTypeFont:
    """폭을 넘으면 글자 크기를 줄인다"""
    while size > 20:
        f = font(size, weight)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return font(size, weight)


def main() -> None:
    icon = Image.open(ICON).convert("RGB").resize((400, 400), Image.LANCZOS)

    for lang, (title, tagline) in VARIANTS.items():
        img = Image.new("RGB", (W, H), BG)
        img.paste(icon, (40, (H - 400) // 2))

        d = ImageDraw.Draw(img, "RGBA")
        left, max_w = 470, W - 470 - 64  # 오른쪽 가장자리는 비워 둔다
        tf = fit(d, title, 88, 800, max_w)
        sf = fit(d, tagline, 40, 500, max_w)

        tb = d.textbbox((0, 0), title, font=tf)
        sb = d.textbbox((0, 0), tagline, font=sf)
        gap = 22
        block = (tb[3] - tb[1]) + gap + (sb[3] - sb[1])
        y = (H - block) // 2

        d.text((left, y - tb[1]), title, font=tf, fill=INK)
        d.text((left, y + (tb[3] - tb[1]) + gap - sb[1]), tagline, font=sf, fill=SUB)

        out = OUT / f"feature-graphic-{lang}.png"
        img.save(out)
        print(out)


if __name__ == "__main__":
    main()
