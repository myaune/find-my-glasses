"""스토어 스크린샷 (노랑 테마) — 1080x1920 세 장.

1 흐릿한 방 (안경 벗은 사람 눈으로 본 모습. 폰 없이, 위 1/4 노랑 아래 3/4 흐린 사진)
2 찾는 화면   3 폭죽 화면
아이콘과 같은 노랑 배경 + 먹색 글자. 제목 아래에 아이콘의 안경 하나.
두 장의 경계마다 아주 크고 흐릿한 안경을 하나씩 걸쳐 둔다 (폰 뒤로 일부 가려진다).

    uv run python scripts/render_store_yellow.py
"""
from __future__ import annotations

import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from render_store_marketing import REL, SS, phone, place, screen

W, H = 1080, 1920
YELLOW = (255, 217, 90)
INK = (43, 43, 48)
FB = r"C:\Windows\Fonts\segoeuib.ttf"

TILES = [
    # (화면, 문구, 폰 기울기). None 은 폰 없이 흐릿한 방.
    (None, ("Everything’s", "a blur?"), 0.0),
    ("screenshot-2-search.png", ("Find your glasses", "without your glasses."), -4.0),
    ("screenshot-1-found.png", ("Found them?", "Fireworks."), 4.0),
]
N = len(TILES)
PHONE_H = 1300
PHONE_Y = 1140
TEXT_Y = (175, 280)
ORNAMENT_Y = 400
PHOTO_TOP = 480           # 1장 사진이 시작하는 높이 (위 1/4 은 노랑)

random.seed(8)


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
        for q in (a, b):
            x, y = P(*q)
            d.ellipse([x - stroke / 2, y - stroke / 2, x + stroke / 2, y + stroke / 2], fill=color)
    return big.resize((w, h), Image.LANCZOS)


def blurry_room(w: int, h: int) -> Image.Image:
    """찾았어요 화면 속 사진(책상)을 화면 가득 키워 알아볼 수 없게 흐린다 — 안경 벗은 눈."""
    found = Image.open(REL / "screenshot-1-found.png").convert("RGB")
    photo = found.crop((90, 700, 810, 1128))            # 찾았어요 화면 속 책상 사진
    # 목표 비율(w:h)에 맞는 세로 조각을 가운데(안경 쪽)에서 오린다
    ch = photo.height
    cw = int(ch * w / h)
    cx = photo.width // 2
    part = photo.crop((cx - cw // 2, 0, cx + cw // 2, ch))
    big = part.resize((w, h), Image.LANCZOS)
    return big.filter(ImageFilter.GaussianBlur(45 * SS))


def main() -> None:
    PW, PH = W * N * SS, H * SS
    canvas = Image.new("RGBA", (PW, PH), YELLOW + (255,))

    # 1장: 위 1/4 은 노랑(제목), 아래 3/4 을 흐린 사진으로 꽉 채운다
    room = blurry_room(W * SS, PH - PHOTO_TOP * SS)
    canvas.paste(room, (0, PHOTO_TOP * SS))

    # 폰은 따로 그려 두고, 폰 자리를 경계 안경이 피하게 한다
    phones = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    for i, (name, _, ang) in enumerate(TILES):
        if name:
            place(phones, phone(screen(name), PHONE_H * SS), (i * W + W // 2) * SS, PHONE_Y * SS, ang)
    busy = phones.split()[3].point(lambda a: 255 if a > 20 else 0).filter(ImageFilter.MaxFilter(41))

    # 경계마다 아주 큰 흐릿한 안경 하나 — 두 장에 반씩 걸친다. 폰 뒤로 일부 가려진다.
    for seam in range(1, N):
        gw = int(random.uniform(950, 1150) * SS)
        ang = random.uniform(25, 45) * random.choice((1, -1))
        spr = glasses_sprite(gw, INK + (60,)).rotate(ang, resample=Image.BICUBIC, expand=True)
        spr = spr.filter(ImageFilter.GaussianBlur(10 * SS))
        cx = seam * W * SS
        cy = random.randint(900, 1250) * SS
        canvas.alpha_composite(spr, (cx - spr.width // 2, cy - spr.height // 2))

    canvas.alpha_composite(phones)

    f = ImageFont.truetype(FB, 80 * SS)
    d = ImageDraw.Draw(canvas)
    orn_ink = glasses_sprite(130 * SS, INK + (170,))
    orn_white = glasses_sprite(130 * SS, (255, 255, 255, 220))
    for i, (name, (l1, l2), _) in enumerate(TILES):
        cx = (i * W + W // 2) * SS
        col = INK
        d.text((cx, TEXT_Y[0] * SS), l1, font=f, fill=col, anchor="mm")
        d.text((cx, TEXT_Y[1] * SS), l2, font=f, fill=col, anchor="mm")
        orn = orn_ink
        canvas.alpha_composite(orn, (cx - orn.width // 2, ORNAMENT_Y * SS - orn.height // 2))

    full = canvas.convert("RGB").resize((W * N, H), Image.LANCZOS)
    full.save(REL / "store-yellow-spread.png")
    for i in range(N):
        p = REL / f"store-yellow-{i + 1}.png"
        full.crop((i * W, 0, (i + 1) * W, H)).save(p)
        print(p)


if __name__ == "__main__":
    main()
