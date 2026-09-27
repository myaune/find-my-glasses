"""스토어용 광고형 스크린샷 두 장 (1080x1920).

위에 짧은 문구, 아래에 비스듬한 폰 목업. 두 장을 나란히 놓으면 배경의 빛과 색종이가
이어져 한 장처럼 보이게, 2160x1920 한 판에 그린 뒤 반으로 자른다.
폰 화면은 render_store_screenshots.py 가 만든 두 장을 쓴다.

    uv run python scripts/render_store_marketing.py
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REL = Path(__file__).resolve().parents[2] / "docs" / "release"
W, H = 1080, 1920
SS = 2                                   # 2배로 그린 뒤 줄인다

BG_TOP = (24, 26, 33)
BG_BOTTOM = (11, 12, 16)
ACCENT = (168, 199, 250)
WHITE = (255, 255, 255)
FONT_B = r"C:\Windows\Fonts\segoeuib.ttf"

TILES = [
    # (화면, 문구 1줄, 문구 2줄(강조색), 폰 기울기, 폰 가운데 x)
    ("screenshot-2-search.png", "Can’t see your glasses?", "Your phone can.", -7.0, 520),
    ("screenshot-1-found.png", "Found them.", "Have some fireworks.", 7.0, 560),
]

random.seed(11)


def screen(name: str) -> Image.Image:
    """두 화면의 비율을 맞춘다 (900x1760). 짧은 쪽은 아래를 검게 채운다 (내비게이션 자리)."""
    im = Image.open(REL / name).convert("RGB")
    if im.height < 1760:
        # 검게 채우면 폰 아래에 띠가 생긴다. 맨 아래 버튼 밑 바닥 줄(26px)만 거울로
        # 번갈아 이어 붙인다. 버튼까지 비추면 거꾸로 된 버튼이 보인다.
        extra = 1760 - im.height
        band = im.crop((0, im.height - 26, 900, im.height))
        flip = band.transpose(Image.FLIP_TOP_BOTTOM)
        pad = Image.new("RGB", (900, 1760))
        pad.paste(im, (0, 0))
        y, k = im.height, 0
        while y < 1760:
            pad.paste(flip if k % 2 == 0 else band, (0, y))
            y += band.height
            k += 1
        im = pad
    return im


def phone(scr: Image.Image, height: int) -> Image.Image:
    """폰 목업 한 대 (RGBA). 검은 몸체 + 얇은 테 + 가운데 카메라 구멍."""
    bezel = int(height * 0.018)
    sh = height - 2 * bezel
    sw = int(sh * scr.width / scr.height)
    w = sw + 2 * bezel
    r_body = int(w * 0.13)
    r_scr = r_body - bezel

    body = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    d.rounded_rectangle([0, 0, w - 1, height - 1], radius=r_body, fill=(18, 18, 20, 255))
    d.rounded_rectangle([2, 2, w - 3, height - 3], radius=r_body - 2, outline=(70, 72, 80, 255), width=3)

    s = scr.resize((sw, sh), Image.LANCZOS)
    m = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, sw - 1, sh - 1], radius=r_scr, fill=255)
    body.paste(s, (bezel, bezel), m)

    cam = int(w * 0.028)
    cx = w // 2
    cy = bezel + int(sh * 0.018)
    d.ellipse([cx - cam, cy - cam, cx + cam, cy + cam], fill=(8, 8, 10, 255))
    return body


def place(canvas: Image.Image, ph: Image.Image, cx: int, cy: int, angle: float):
    rot = ph.rotate(angle, resample=Image.BICUBIC, expand=True)
    # 그림자 — 아래로 조금 내려 흐리게. 흐림이 잘려 네모 자국이 남지 않게 여백을 두고 흐린다.
    pad = 160 * SS
    shadow = Image.new("RGBA", (rot.width + 2 * pad, rot.height + 2 * pad), (0, 0, 0, 0))
    a = Image.new("L", shadow.size, 0)
    a.paste(rot.split()[3].point(lambda v: int(v * 0.55)), (pad, pad))
    shadow.putalpha(a.filter(ImageFilter.GaussianBlur(40 * SS)))
    x = cx - rot.width // 2
    y = cy - rot.height // 2
    # 캔버스 밖으로 나가는 부분은 잘라서 붙인다 (alpha_composite 는 음수 좌표를 못 받는다)
    for layer, (lx, ly) in ((shadow, (x - pad + 10 * SS, y - pad + 40 * SS)), (rot, (x, y))):
        l0, t0 = max(0, -lx), max(0, -ly)
        canvas.alpha_composite(layer.crop((l0, t0, layer.width, layer.height)), (lx + l0, ly + t0))


def star(d, cx, cy, r, points, inner, fill):
    pts = []
    for i in range(points * 2):
        a = math.pi * i / points - math.pi / 2
        rr = r if i % 2 == 0 else r * inner
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    d.polygon(pts, fill=fill)


def main() -> None:
    PW, PH = W * 2 * SS, H * SS
    canvas = Image.new("RGBA", (PW, PH))

    # 배경 — 위에서 아래로 살짝 어두워진다
    grad = Image.new("RGB", (1, PH))
    for y in range(PH):
        t = y / (PH - 1)
        grad.putpixel((0, y), tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)))
    canvas.paste(grad.resize((PW, PH)), (0, 0))

    # 이음새를 가로지르는 은은한 빛 두 개 — 두 장이 한 판처럼 이어진다
    glow = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for (cx, cy, r, col, a) in ((W * SS, 1150 * SS, 820 * SS, ACCENT, 60),
                                (int(W * 1.55 * SS), 700 * SS, 520 * SS, (255, 190, 215), 34),
                                (int(W * 0.35 * SS), 1500 * SS, 560 * SS, ACCENT, 30)):
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (a,))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(160 * SS)))

    # 색종이·별 — 이음새 근처와 두 번째 장 위쪽에 흩뿌린다
    fx = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    d = ImageDraw.Draw(fx)
    colors = [(255, 214, 0), (255, 138, 0), (255, 45, 85), ACCENT, (140, 230, 140), (200, 140, 255)]
    gold = [(255, 236, 140), (255, 214, 0), (255, 255, 255)]
    for _ in range(46):
        # 이음새(x=1080) 주변에 몰리게
        x = random.gauss(W * 1.0, 170) * SS
        y = random.uniform(420, 1850) * SS
        if random.random() < 0.3:
            star(d, x, y, random.uniform(8, 16) * SS, 5 if random.random() < 0.5 else 4,
                 0.45 if random.random() < 0.5 else 0.22, random.choice(gold) + (230,))
            continue
        w, h = random.uniform(14, 26) * SS, random.uniform(8, 14) * SS
        piece = Image.new("RGBA", (int(60 * SS), int(60 * SS)), (0, 0, 0, 0))
        c = 30 * SS
        ImageDraw.Draw(piece).rectangle([c - w / 2, c - h / 2, c + w / 2, c + h / 2],
                                        fill=random.choice(colors) + (220,))
        piece = piece.rotate(random.uniform(0, 180), resample=Image.BICUBIC)
        fx.alpha_composite(piece, (int(x - c), int(y - c)))
    canvas.alpha_composite(fx)

    # 폰
    ph_h = int(1290 * SS)
    for i, (name, _, _, ang, cx) in enumerate(TILES):
        place(canvas, phone(screen(name), ph_h), (i * W + cx) * SS, 1180 * SS, ang)


    # 문구 — 장마다 위쪽 가운데
    d = ImageDraw.Draw(canvas)
    f = ImageFont.truetype(FONT_B, 76 * SS)
    for i, (_, l1, l2, _, _) in enumerate(TILES):
        cx = (i * W + W // 2) * SS
        d.text((cx, 170 * SS), l1, font=f, fill=WHITE, anchor="mm")
        d.text((cx, 265 * SS), l2, font=f, fill=ACCENT, anchor="mm")

    full = canvas.convert("RGB").resize((W * 2, H), Image.LANCZOS)
    full.save(REL / "store-spread.png")
    for i in range(2):
        p = REL / f"store-{i + 1}.png"
        full.crop((i * W, 0, (i + 1) * W, H)).save(p)
        print(p)


if __name__ == "__main__":
    main()
