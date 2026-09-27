"""스토어 파노라마 스크린샷 두 장 (1080x1920).

폰 한 대가 두 장의 경계선을 걸치고 서서 각 장에 거의 절반씩 보인다. 1장에서 반쪽을
보고, 넘기면 나머지가 보인다. 2160x1920 한 판에 그린 뒤 반으로 자른다.
문구는 장마다 위에 따로 둔다 (한 장만 봐도 말이 되게).
경계선이 안경 박스를 자르지 않게, 폰을 1장 쪽으로 조금 치우친다.

    uv run python scripts/render_store_split.py
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from render_store_marketing import (
    ACCENT, BG_BOTTOM, BG_TOP, FONT_B, REL, SS, WHITE, H, W, phone, place, screen, star,
)

SCREEN = "screenshot-2-search.png"
PHONE_H = 1900          # 폰 긴 변 (px, 1080 폭 기준) — 두 장 폭을 거의 다 쓴다
ANGLE = -60.0           # 크게 눕힌다 (위가 오른쪽 위)
CENTER = (1310, 1230)   # 경계선이 폰 길이의 약 64% 지점 — 안경 박스는 2장, 버튼 쪽은 1장

LINES = [("Can’t see", "your glasses?"),         # 1장 (둘째 줄 강조색)
         ("Your phone", "can.")]                  # 2장

random.seed(5)


def main() -> None:
    PW, PH = W * 2 * SS, H * SS
    canvas = Image.new("RGBA", (PW, PH))

    grad = Image.new("RGB", (1, PH))
    for y in range(PH):
        t = y / (PH - 1)
        grad.putpixel((0, y), tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)))
    canvas.paste(grad.resize((PW, PH)), (0, 0))

    # 폰 뒤로 은은한 빛 — 폰을 따라 비스듬히
    glow = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for (cx, cy, r, col, a) in ((700, 1450, 620, ACCENT, 55), (1450, 560, 560, (255, 190, 215), 40),
                                (1080, 1000, 760, ACCENT, 35)):
        gd.ellipse([(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS], fill=col + (a,))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(170 * SS)))

    # 색종이·별 — 폰 뒤, 문구와 겹치지 않게
    fx = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    d = ImageDraw.Draw(fx)
    colors = [(255, 214, 0), (255, 138, 0), (255, 45, 85), ACCENT, (140, 230, 140), (200, 140, 255)]
    gold = [(255, 236, 140), (255, 214, 0), (255, 255, 255)]
    placed = 0
    while placed < 44:
        x, y = random.uniform(40, 2120), random.uniform(60, 1880)
        if y < 400:                          # 문구 자리
            continue
        placed += 1
        x, y = x * SS, y * SS
        if random.random() < 0.3:
            star(d, x, y, random.uniform(9, 17) * SS, 5 if random.random() < 0.5 else 4,
                 0.45 if random.random() < 0.5 else 0.22, random.choice(gold) + (230,))
            continue
        w, h = random.uniform(14, 26) * SS, random.uniform(8, 14) * SS
        piece = Image.new("RGBA", (60 * SS, 60 * SS), (0, 0, 0, 0))
        c = 30 * SS
        ImageDraw.Draw(piece).rectangle([c - w / 2, c - h / 2, c + w / 2, c + h / 2],
                                        fill=random.choice(colors) + (220,))
        fx.alpha_composite(piece.rotate(random.uniform(0, 180), resample=Image.BICUBIC),
                           (int(x - c), int(y - c)))
    canvas.alpha_composite(fx)

    place(canvas, phone(screen(SCREEN), PHONE_H * SS), CENTER[0] * SS, CENTER[1] * SS, ANGLE)

    d = ImageDraw.Draw(canvas)
    f = ImageFont.truetype(FONT_B, 92 * SS)
    for i, (l1, l2) in enumerate(LINES):
        cx = (i * W + W // 2) * SS
        d.text((cx, 185 * SS), l1, font=f, fill=WHITE, anchor="ms")
        d.text((cx, 295 * SS), l2, font=f, fill=ACCENT, anchor="ms")

    full = canvas.convert("RGB").resize((W * 2, H), Image.LANCZOS)
    full.save(REL / "store-split-spread.png")
    for i in range(2):
        p = REL / f"store-split-{i + 1}.png"
        full.crop((i * W, 0, (i + 1) * W, H)).save(p)
        print(p)


if __name__ == "__main__":
    main()
