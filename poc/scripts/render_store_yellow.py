"""스토어 스크린샷 (노랑 테마) — 1080x1920 세 장.

1 흐릿함 (안경 없이 보는 세상) → 2 찾는 화면 → 3 폭죽.

아이콘과 같은 노랑 배경 + 먹색 글자. 제목 아래에 아이콘의 안경 세 개를 한 줄로 둔다
(장식. 폰·글자·경계에 걸리지 않는다).
문구는 짧게.

    uv run python scripts/render_store_yellow.py
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from render_store_marketing import REL, SS, phone, place, screen

W, H = 1080, 1920
YELLOW = (255, 217, 90)
INK = (43, 43, 48)
FB = r"C:\Windows\Fonts\segoeuib.ttf"

TILES = [
    # (화면, 문구, 폰 기울기). "blur" 는 찾은 사진을 크게 오려 심하게 흐린 화면.
    ("blur", ("Everything’s", "a blur?"), 4.0),
    ("screenshot-2-search.png", ("Find your glasses", "without your glasses."), -4.0),
    ("screenshot-1-found.png", ("Found them?", "Fireworks."), 4.0),
]
PHONE_H = 1300
PHONE_Y = 1230
TEXT_Y = (175, 280)
ORNAMENT_Y = 400        # 제목과 폰 사이
N = len(TILES)

random.seed(21)


def glasses_sprite(width: int, color) -> Image.Image:
    """아이콘의 안경 (108 격자, x 20~88 / y 44~65) 을 폭 width 로 그린 조각."""
    k = width / 68.0
    pad = int(6 * k)
    w, h = int(68 * k) + 2 * pad, int(21 * k) + 2 * pad
    big = Image.new("RGBA", (w * 4, h * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    s = 4 * k
    stroke = max(2, int(3.4 * s))

    def P(x, y):
        return (x - 20) * s + pad * 4, (y - 44) * s + pad * 4

    for x0 in (27, 57):
        d.rounded_rectangle([*P(x0, 45.5), *P(x0 + 24, 63.5)], radius=8 * s, outline=color, width=stroke)
    pts = []
    for i in range(25):
        t = i / 24
        pts.append(P((1 - t) ** 2 * 51 + 2 * (1 - t) * t * 54 + t ** 2 * 57,
                     (1 - t) ** 2 * 51.5 + 2 * (1 - t) * t * 47.5 + t ** 2 * 51.5))
    d.line(pts, fill=color, width=stroke, joint="curve")
    for a, b in (((27, 50), (22, 48)), ((81, 50), (86, 48))):
        d.line([P(*a), P(*b)], fill=color, width=stroke)
        for q in (a, b):   # 둥근 끝
            x, y = P(*q)
            d.ellipse([x - stroke / 2, y - stroke / 2, x + stroke / 2, y + stroke / 2], fill=color)
    return big.resize((w, h), Image.LANCZOS)


def blur_screen() -> Image.Image:
    """찾았어요 화면 속 사진(안경이 있는 책상)만 오려 화면 가득 키우고 알아볼 수 없게 흐린다."""
    found = Image.open(REL / "screenshot-1-found.png").convert("RGB")
    photo = found.crop((90, 700, 810, 1128))          # 테두리 안 사진 부분
    tw, th = 900, 1760
    s = max(tw / photo.width, th / photo.height)
    big = photo.resize((int(photo.width * s), int(photo.height * s)), Image.LANCZOS)
    x = (big.width - tw) // 2
    big = big.crop((x, 0, x + tw, th))
    return big.filter(ImageFilter.GaussianBlur(55))


def screen_for(name: str) -> Image.Image:
    return blur_screen() if name == "blur" else screen(name)


def main() -> None:
    PW, PH = W * N * SS, H * SS
    canvas = Image.new("RGBA", (PW, PH), YELLOW + (255,))

    # 폰은 따로 그려 두고, 폰이 차지한 자리를 안경이 피하게 한다
    phones = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    for i, (name, _, ang) in enumerate(TILES):
        place(phones, phone(screen_for(name), PHONE_H * SS), (i * W + W // 2) * SS, PHONE_Y * SS, ang)
    busy = phones.split()[3].point(lambda a: 255 if a > 20 else 0).filter(ImageFilter.MaxFilter(61))

    f = ImageFont.truetype(FB, 80 * SS)
    d_busy = ImageDraw.Draw(busy)
    for i, (_, (l1, l2), _) in enumerate(TILES):
        cx = (i * W + W // 2) * SS
        for line, y in zip((l1, l2), TEXT_Y):
            x0, y0, x1, y1 = ImageDraw.Draw(canvas).textbbox((cx, y * SS), line, font=f, anchor="mm")
            d_busy.rectangle([x0 - 40 * SS, y0 - 40 * SS, x1 + 40 * SS, y1 + 40 * SS], fill=255)

    # 안경 장식 — 장마다 제목 아래에 같은 크기 세 개를 한 줄로 가지런히 (세 장 모두 같은 자리)
    gw, gap, gy = 120 * SS, 46 * SS, ORNAMENT_Y * SS
    spr = glasses_sprite(gw, INK + (150,))
    placed = []
    for i in range(N):
        cx = (i * W + W // 2) * SS
        total = 3 * spr.width + 2 * gap
        x = cx - total // 2
        for j in range(3):
            canvas.alpha_composite(spr, (x + j * (spr.width + gap), gy - spr.height // 2))
            placed.append((i, j))

    canvas.alpha_composite(phones)
    d = ImageDraw.Draw(canvas)
    for i, (_, (l1, l2), _) in enumerate(TILES):
        cx = (i * W + W // 2) * SS
        d.text((cx, TEXT_Y[0] * SS), l1, font=f, fill=INK, anchor="mm")
        d.text((cx, TEXT_Y[1] * SS), l2, font=f, fill=INK, anchor="mm")

    full = canvas.convert("RGB").resize((W * N, H), Image.LANCZOS)
    full.save(REL / "store-yellow-spread.png")
    for i in range(N):
        p = REL / f"store-yellow-{i + 1}.png"
        full.crop((i * W, 0, (i + 1) * W, H)).save(p)
        print(p)
    print("glasses placed:", len(placed))


if __name__ == "__main__":
    main()
