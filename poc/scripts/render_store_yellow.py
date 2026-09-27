"""스토어 스크린샷 (노랑 테마) — 1080x1920 세 장.

1 흐릿한 방 (안경 벗은 사람 눈으로 본 모습. 폰도 안경도 없이. 위 노랑이 사진으로 스르륵 이어진다)
2 찾는 화면   3 폭죽 화면
아이콘과 같은 노랑 배경 + 먹색 글자. 2·3장 제목 아래에 아이콘의 안경 하나.
2·3장 배경에는 크고 작은 안경을 옅게 깐 패턴 (1장에는 없다).

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
PHOTO_FADE = (330, 820)   # 1장: 이 높이 사이에서 노랑 → 사진으로 스르륵 바뀐다

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

    # 1장: 흐린 사진을 깔고, 위쪽은 노랑에서 사진으로 부드럽게 넘어간다
    top = PHOTO_FADE[0] * SS
    room = blurry_room(W * SS, PH - top).convert("RGBA")
    fade = Image.new("L", room.size, 255)
    fd = ImageDraw.Draw(fade)
    span = (PHOTO_FADE[1] - PHOTO_FADE[0]) * SS
    for y in range(span):
        t = y / span
        fd.line([(0, y), (room.width, y)], fill=int(255 * (t * t * (3 - 2 * t))))
    room.putalpha(fade)
    canvas.alpha_composite(room, (0, top))

    # 폰은 따로 그려 두고, 폰 자리를 경계 안경이 피하게 한다
    phones = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    for i, (name, _, ang) in enumerate(TILES):
        if name:
            place(phones, phone(screen(name), PHONE_H * SS), (i * W + W // 2) * SS, PHONE_Y * SS, ang)
    busy = phones.split()[3].point(lambda a: 255 if a > 20 else 0).filter(ImageFilter.MaxFilter(41))

    # 2·3장 배경 안경 패턴 — 들쭉날쭉한 격자에 크고 작은 안경. 큰 것은 살짝 흐리게.
    # 1장(흐린 방)으로는 넘어가지 않는다. 제목 자리는 비운다.
    cell = 300 * SS
    x_start = W * SS
    pattern = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    for row in range(PH // cell + 1):
        for col in range((PW - x_start) // cell + 1):
            big = random.random() < 0.35
            gw = int((random.uniform(260, 360) if big else random.uniform(110, 170)) * SS)
            ang = random.uniform(-30, 30)
            spr = glasses_sprite(gw, INK + (45 if big else 60,)).rotate(ang, resample=Image.BICUBIC, expand=True)
            if big:
                spr = spr.filter(ImageFilter.GaussianBlur(4 * SS))
            ox = (cell // 2) * (row % 2)                      # 줄마다 반 칸 어긋나게
            cx = x_start + col * cell + ox + random.randint(-50, 50) * SS
            cy = row * cell + cell // 2 + random.randint(-50, 50) * SS
            x, y = cx - spr.width // 2, cy - spr.height // 2
            if x < x_start + 20 * SS or cy < 470 * SS:        # 1장 쪽, 제목 자리
                continue
            pattern.alpha_composite(spr, (max(0, x), max(0, y)))
    canvas.alpha_composite(pattern)

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
        if name is not None:
            canvas.alpha_composite(orn_ink, (cx - orn_ink.width // 2, ORNAMENT_Y * SS - orn_ink.height // 2))

    full = canvas.convert("RGB").resize((W * N, H), Image.LANCZOS)
    full.save(REL / "store-yellow-spread.png")
    for i in range(N):
        p = REL / f"store-yellow-{i + 1}.png"
        full.crop((i * W, 0, (i + 1) * W, H)).save(p)
        print(p)


if __name__ == "__main__":
    main()
