"""스토어 스크린샷 (노랑 테마) — 1080x1920 세 장.

1 흐릿한 방 (안경 벗은 사람 눈으로 본 모습. 폰 없이 배경 전체, 오른쪽으로 노랑에 스며든다)
2 찾는 화면   3 폭죽 화면
아이콘과 같은 노랑 배경 + 먹색 글자. 제목 아래에 아이콘의 안경 하나.
두 장의 경계에는 크고 흐릿한 안경을 몇 개 걸쳐 둔다 (폰에 가리지 않는 빈 틈에).

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
PHONE_Y = 1230
TEXT_Y = (175, 280)
ORNAMENT_Y = 400
SEAM_GLASSES = 2          # 경계마다

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
    photo = found.crop((90, 700, 810, 1128))
    s = max(w / photo.width, h / photo.height)
    big = photo.resize((int(photo.width * s) + 2, int(photo.height * s) + 2), Image.LANCZOS)
    x = (big.width - w) // 2
    return big.crop((x, 0, x + w, h)).filter(ImageFilter.GaussianBlur(60 * SS))


def main() -> None:
    PW, PH = W * N * SS, H * SS
    canvas = Image.new("RGBA", (PW, PH), YELLOW + (255,))

    # 1장: 흐릿한 방. 오른쪽 끝 360px 에서 노랑으로 스며든다 (2장과 이어지게)
    room = blurry_room(W * SS, PH).convert("RGBA")
    room.alpha_composite(Image.new("RGBA", room.size, (0, 0, 0, 60)))       # 글자가 읽히게 살짝 어둡게
    fade = Image.new("L", room.size, 255)
    fd = ImageDraw.Draw(fade)
    f0 = (W - 360) * SS
    for x in range(f0, W * SS):
        t = (x - f0) / (W * SS - f0)
        fd.line([(x, 0), (x, PH)], fill=int(255 * (1 - t) ** 1.5))
    room.putalpha(fade)
    canvas.alpha_composite(room, (0, 0))

    # 폰은 따로 그려 두고, 폰 자리를 경계 안경이 피하게 한다
    phones = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    for i, (name, _, ang) in enumerate(TILES):
        if name:
            place(phones, phone(screen(name), PHONE_H * SS), (i * W + W // 2) * SS, PHONE_Y * SS, ang)
    busy = phones.split()[3].point(lambda a: 255 if a > 20 else 0).filter(ImageFilter.MaxFilter(41))

    # 경계에 걸친 크고 흐릿한 안경 — 폰 사이 빈 틈, 위아래로 나눠서
    seam_layer = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    bd = ImageDraw.Draw(busy)
    for seam in range(1, N):
        sx = seam * W * SS
        for band in range(SEAM_GLASSES):
            y_lo = (560 + band * 700) * SS
            y_hi = (560 + band * 700 + 600) * SS
            for _ in range(400):
                gw = int(random.uniform(300, 470) * SS)
                ang = random.uniform(25, 60) * random.choice((1, -1))   # 세로로 세우면 쇠사슬처럼 보인다
                spr = glasses_sprite(gw, INK + (70,)).rotate(ang, resample=Image.BICUBIC, expand=True)
                spr = spr.filter(ImageFilter.GaussianBlur(7 * SS))
                cx = sx + random.randint(-50, 50) * SS
                cy = random.randint(y_lo, y_hi)
                x, y = cx - spr.width // 2, cy - spr.height // 2
                if y < 0 or y + spr.height > PH:
                    continue
                # 폰과 겹치는지 — 안경 모양 그대로 확인
                m = spr.split()[3].point(lambda a: 255 if a > 10 else 0)
                region = busy.crop((x, y, x + spr.width, y + spr.height))
                hit = Image.composite(region, Image.new("L", region.size, 0), m).getbbox()
                if hit:
                    continue
                seam_layer.alpha_composite(spr, (x, y))
                bd.rectangle([x, y, x + spr.width, y + spr.height], fill=255)   # 서로 안 겹치게
                break
    canvas.alpha_composite(seam_layer)

    canvas.alpha_composite(phones)

    f = ImageFont.truetype(FB, 80 * SS)
    d = ImageDraw.Draw(canvas)
    orn_ink = glasses_sprite(130 * SS, INK + (170,))
    orn_white = glasses_sprite(130 * SS, (255, 255, 255, 220))
    for i, (name, (l1, l2), _) in enumerate(TILES):
        cx = (i * W + W // 2) * SS
        col = (255, 255, 255) if name is None else INK
        d.text((cx, TEXT_Y[0] * SS), l1, font=f, fill=col, anchor="mm")
        d.text((cx, TEXT_Y[1] * SS), l2, font=f, fill=col, anchor="mm")
        orn = orn_white if name is None else orn_ink
        canvas.alpha_composite(orn, (cx - orn.width // 2, ORNAMENT_Y * SS - orn.height // 2))

    full = canvas.convert("RGB").resize((W * N, H), Image.LANCZOS)
    full.save(REL / "store-yellow-spread.png")
    for i in range(N):
        p = REL / f"store-yellow-{i + 1}.png"
        full.crop((i * W, 0, (i + 1) * W, H)).save(p)
        print(p)


if __name__ == "__main__":
    main()
