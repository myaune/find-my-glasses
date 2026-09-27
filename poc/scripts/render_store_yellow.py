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
PHONE_Y = 1152
TEXT_Y = (175, 280)
ORNAMENT_Y = 400
# 스토어가 스크린샷 사이에 두는 간격 (1080 폭 기준). 정확한 값은 공개된 문서에서 못 찾았다.
# 애플 가이드의 약 5% (1125 폭에 56px) 를 따라 48px 로 둔다. 이 간격에 걸린 그림은 버려진다.
GAP = 48
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


def tile_x(i: int) -> int:
    """i 번째 장의 왼쪽 끝 (디자인 판 좌표, SS 배율 전). 장 사이에 스토어 간격만큼 빈 틈을 둔다."""
    return i * (W + GAP)


def main() -> None:
    PW, PH = (W * N + GAP * (N - 1)) * SS, H * SS
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

    phones = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    for i, (name, _, ang) in enumerate(TILES):
        if name:
            place(phones, phone(screen(name), PHONE_H * SS), (tile_x(i) + W // 2) * SS, PHONE_Y * SS, ang)

    # 2·3장 배경 안경 — 개수는 적게, 크기 차이는 크게. 안경마다 흐림·진하기를 다르게 준다.
    # 1장으로는 넘어가지 않고, 제목 자리는 비운다.
    # 2|3 사이 간격에 걸친 안경은 간격 부분이 버려져서, 스토어에서 나란히 보면 이어져 보인다.
    x_lo = (tile_x(1) + 30) * SS
    x_hi = PW
    pattern = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    placed = []

    def sprite(gw_px: float, ang: float) -> Image.Image:
        alpha = int(random.uniform(28, 95))                     # 진하기 (회색 정도)
        blur = random.choice((0, 0, 2, 4, 7, 11))               # 흐림
        spr = glasses_sprite(int(gw_px * SS), INK + (alpha,)).rotate(ang, resample=Image.BICUBIC, expand=True)
        return spr.filter(ImageFilter.GaussianBlur(blur * SS)) if blur else spr

    def put(spr: Image.Image, cx: float, cy: float) -> None:
        pattern.alpha_composite(spr, (int(cx - spr.width / 2), max(0, int(cy - spr.height / 2))))
        placed.append((cx, cy, max(spr.width, spr.height) / 2))

    def free(cx: float, cy: float, r: float) -> bool:
        return all((cx - px) ** 2 + (cy - py) ** 2 >= ((r + pr) * 0.75) ** 2 for px, py, pr in placed)

    # 1) 2|3 경계에 걸친 큰 안경 — 많이 기울여서
    for cy in (random.uniform(820, 1000), random.uniform(1480, 1620)):
        spr = sprite(random.uniform(560, 720), random.uniform(35, 60) * random.choice((1, -1)))
        put(spr, (tile_x(2) - GAP / 2) * SS, cy * SS)

    # 2) 2장 왼쪽 빈 띠에 작은·중간 안경 몇 개
    for cy in (620, 1080, 1560):
        for _try in range(100):
            spr = sprite(random.uniform(90, 220), random.uniform(-35, 35))
            r = max(spr.width, spr.height) / 2
            cx = random.uniform(x_lo + spr.width / 2, (tile_x(1) + 230) * SS)
            y = (cy + random.uniform(-120, 120)) * SS
            if free(cx, y, r):
                put(spr, cx, y)
                break

    # 3) 나머지 — 아주 큰 것 / 중간 / 작은 것을 흩어서
    for lo, hi, count in ((560, 760, 2), (260, 360, 3), (90, 140, 5)):
        for _ in range(count):
            for _try in range(300):
                spr = sprite(random.uniform(lo, hi), random.uniform(-30, 30))
                r = max(spr.width, spr.height) / 2
                cx = random.uniform(x_lo + spr.width / 2, x_hi - r * 0.3)
                cy = random.uniform(470 * SS + r * 0.5, PH - r * 0.2)
                if free(cx, cy, r):
                    put(spr, cx, cy)
                    break
    canvas.alpha_composite(pattern)
    canvas.alpha_composite(phones)

    f = ImageFont.truetype(FB, 80 * SS)
    d = ImageDraw.Draw(canvas)
    orn = glasses_sprite(130 * SS, INK + (170,))
    for i, (name, (l1, l2), _) in enumerate(TILES):
        cx = (tile_x(i) + W // 2) * SS
        d.text((cx, TEXT_Y[0] * SS), l1, font=f, fill=INK, anchor="mm")
        d.text((cx, TEXT_Y[1] * SS), l2, font=f, fill=INK, anchor="mm")
        if name is not None:
            canvas.alpha_composite(orn, (cx - orn.width // 2, ORNAMENT_Y * SS - orn.height // 2))

    full = canvas.convert("RGB").resize((PW // SS, H), Image.LANCZOS)
    full.save(REL / "store-yellow-spread.png")
    for i in range(N):
        p = REL / f"store-yellow-{i + 1}.png"
        full.crop((tile_x(i), 0, tile_x(i) + W, H)).save(p)
        print(p)
    print("glasses:", len(placed))


if __name__ == "__main__":
    main()
