"""Play 스토어 그래픽 이미지(1024×500) — 아이콘 + 앱 이름만, 가운데 정렬.

아이콘은 render_store_icon.py 로 만든 512px 이미지에서 배경을 뺀 실제 그림 영역만 잘라 쓴다.
아이콘과 글자를 한 덩어리로 보고, 눈에 보이는 가장자리 기준으로 좌우·상하 여백을 같게 둔다.
글꼴은 Noto Sans KR (SIL Open Font License, 상업 이용 가능). 글자는 이미지에 그려 넣는다.

    uv run python scripts/render_store_icon.py
    uv run python scripts/render_feature_graphic.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "release"
ICON = OUT / "icon-512.png"
FONT = Path("C:/Windows/Fonts/NotoSansKR-VF.ttf")

W, H = 1024, 500
BG = (255, 217, 90)  # #FFD95A — 아이콘 배경과 같은 색
INK = (43, 43, 48)

ICON_H = 260   # 아이콘 그림 높이
GAP = 44       # 아이콘과 글자 사이
TITLE_PX = 92
MIN_SIDE = 110 # 좌우 최소 여백

TITLES = {
    "ko": "내 안경 찾기",
    "en": "Find My Glasses",
}


def icon_art() -> Image.Image:
    """배경을 뺀 실제 그림 영역만 잘라낸다"""
    im = Image.open(ICON).convert("RGB")
    diff = ImageChops.difference(im, Image.new("RGB", im.size, BG)).convert("L")
    bbox = diff.point(lambda v: 255 if v > 24 else 0).getbbox()
    art = im.crop(bbox)
    s = ICON_H / art.height
    return art.resize((round(art.width * s), ICON_H), Image.LANCZOS)


def main() -> None:
    art = icon_art()

    for lang, title in TITLES.items():
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)

        # 좌우 여백이 MIN_SIDE 보다 작아지면 글자를 줄인다 (영어 이름이 길다)
        size = TITLE_PX
        while True:
            font = ImageFont.truetype(str(FONT), size)
            font.set_variation_by_axes([800])
            l, t, r, b = d.textbbox((0, 0), title, font=font)
            if art.width + GAP + (r - l) <= W - 2 * MIN_SIDE or size <= 40:
                break
            size -= 2

        # 글자의 실제 잉크 영역 (여백 없이)
        l, t, r, b = d.textbbox((0, 0), title, font=font)
        tw, th = r - l, b - t

        total = art.width + GAP + tw
        x0 = (W - total) // 2
        img.paste(art, (x0, (H - art.height) // 2))

        tx = x0 + art.width + GAP
        # 글자는 돋보기 렌즈 높이(그림 위쪽 약 45%)에 맞춘다
        lens_cy = (H - art.height) // 2 + round(art.height * 0.43)
        d.text((tx - l, lens_cy - th // 2 - t), title, font=font, fill=INK)

        out = OUT / f"feature-graphic-{lang}.png"
        img.save(out)
        print(out, f"left={x0} right={W - (tx + tw)}")


if __name__ == "__main__":
    main()
