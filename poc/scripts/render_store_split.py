"""스토어 스크린샷 두 장 (1080x1920) — 폰 한 대를 크게 비스듬히 눕혀 두 장에 걸치게 한다.

2160x1920 한 판에 그린 뒤 반으로 자른다. 스토어에서 두 장을 나란히 넘겨 보면
폰 한 대가 이어져 보인다. 폰은 왼쪽 아래에서 오른쪽 위로 눕힌다.
문구는 비는 자리에 둔다: 1장은 위, 2장은 아래.

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
PHONE_H = 1720          # 폰 긴 변 (px, 1080 폭 기준)
ANGLE = -38.0           # 시계 방향으로 눕힌다 (위가 오른쪽)
CENTER = (800, 1070)    # 안경 박스가 1장 안에 온전히 들어오게 이음새 왼쪽에

TOP_LINES = ("Can’t see", "your glasses?")        # 1장 위 왼쪽
BOTTOM_LINES = ("Your phone", "can.")             # 2장 아래 오른쪽 (둘째 줄 강조색)

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
        if x < 1000 and y < 520:            # 1장 문구 자리
            continue
        if x > 1160 and y > 1400:           # 2장 문구 자리
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
    f = ImageFont.truetype(FONT_B, 104 * SS)
    lh = 124 * SS
    x0, y0 = 90 * SS, 150 * SS
    d.text((x0, y0), TOP_LINES[0], font=f, fill=WHITE, anchor="ls")
    d.text((x0, y0 + lh), TOP_LINES[1], font=f, fill=WHITE, anchor="ls")
    x1, y1 = (2 * W - 90) * SS, (H - 150) * SS
    d.text((x1, y1 - lh), BOTTOM_LINES[0], font=f, fill=WHITE, anchor="rs")
    d.text((x1, y1), BOTTOM_LINES[1], font=f, fill=ACCENT, anchor="rs")

    full = canvas.convert("RGB").resize((W * 2, H), Image.LANCZOS)
    full.save(REL / "store-split-spread.png")
    for i in range(2):
        p = REL / f"store-split-{i + 1}.png"
        full.crop((i * W, 0, (i + 1) * W, H)).save(p)
        print(p)


if __name__ == "__main__":
    main()
