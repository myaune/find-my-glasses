"""스토어 스크린샷 두 장을 만든다 (폰에서 찍은 예전 버전 화면 → 지금 버전 모양으로).

- 상태바, 내비게이션바, 하단 테스트 광고 줄을 잘라낸다 (900x1696, Play 의 2:1 제한 안).
- 찾는 화면: 찾았어요 버튼을 강조색(연파랑)으로, "다른 물건" 버튼을 지금 자리(가운데 아래)로,
  "이거 아니에요" 를 버튼 위에 넣는다. 예전 "다른 물건" 자리는 주변 배경으로 메운다.
- 찾았어요 화면: 노란 제목·테두리를 지금 색(흰 글자+파란 빛, 파란 테두리)으로 바꾸고
  지금 버전의 연출(숨쉬는 빛, 충격파, 불꽃, 반짝이, 색종이)을 합성한다.

    uv run python scripts/render_store_screenshots.py <찾는화면.jpg> <찾았어요화면.jpg>
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parents[2] / "docs" / "release"
TOP, BOTTOM = 80, 1776           # 상태바 아래 ~ 광고 줄 위
FOUND_BOTTOM = 1840             # 찾았어요 화면은 사진 테두리 아래까지
DP = 2.5                         # 이 폰 스크린샷의 1dp = 2.5px (900px / 360dp)

ACCENT = (168, 199, 250)
ON_ACCENT = (15, 28, 46)
FONT_SB = r"C:\Windows\Fonts\seguisb.ttf"

random.seed(7)


def remap(region: np.ndarray, src_bg, src_fg, dst_bg, dst_fg) -> np.ndarray:
    """두 색(배경·글자) 사이 섞임 비율을 유지한 채 새 두 색으로 바꾼다 (안티앨리어싱 보존)."""
    bg = np.array(src_bg, float)
    fg = np.array(src_fg, float)
    d = fg - bg
    t = ((region.astype(float) - bg) @ d) / (d @ d)
    t = np.clip(t, 0, 1)[..., None]
    return (np.array(dst_bg, float) * (1 - t) + np.array(dst_fg, float) * t).astype(np.uint8)


def search_screen(src: Path) -> Image.Image:
    a = np.asarray(Image.open(src).convert("RGB")).copy()

    # ── 찾았어요 버튼: 보라 → 강조색. 버튼 모양(둥근 사각형) 안쪽만 바꾼다
    band = a[1480:1650]
    purple = (np.abs(band.astype(int) - (208, 188, 252)).sum(2) < 60)
    ys, xs = np.where(purple)
    bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min() + 1480, ys.max() + 1480
    btn = a[by0:by1 + 1, bx0:bx1 + 1]
    bh, bw = btn.shape[:2]
    # 버튼은 알약 모양이다. 색이 아니라 모양으로 마스크를 만든다 (4배로 그려 가장자리를 부드럽게)
    big = Image.new("L", (bw * 4, bh * 4), 0)
    ImageDraw.Draw(big).rounded_rectangle([0, 0, bw * 4 - 1, bh * 4 - 1], radius=bh * 2, fill=255)
    bmask = big.resize((bw, bh), Image.LANCZOS)
    inside = np.asarray(bmask) > 0
    new = remap(btn, (208, 188, 252), (55, 32, 112), ACCENT, ON_ACCENT)
    btn[inside] = new[inside]
    button = Image.fromarray(btn.copy())

    # ── 비는 자리를 주변 배경을 거울처럼 비춰서 메운다 (번지지 않고 무늬가 이어진다).
    # 버튼 모양 안쪽만 메우고 가장자리는 부드럽게 섞는다. 네모로 메우면 경계가 보인다.
    orig = np.asarray(Image.open(src).convert("RGB"))
    H0, W0 = orig.shape[:2]

    def pill_mask(x0, y0, x1, y1, grow):
        m = Image.new("L", (W0, H0), 0)
        ImageDraw.Draw(m).rounded_rectangle(
            [x0 - grow, y0 - grow, x1 + grow, y1 + grow], radius=(y1 - y0) / 2 + grow, fill=255)
        return np.asarray(m.filter(ImageFilter.GaussianBlur(2))).astype(float)[..., None] / 255

    # 옮기는 찾았어요 버튼 자리 — 버튼 바로 아래 배경을 위아래로 비춘다
    seam = by1 + 4
    ys_ = np.arange(H0)
    src_y = np.clip(2 * seam - ys_, 0, H0 - 1)
    mirror_v = orig[src_y]
    m1 = pill_mask(bx0, by0, bx1, by1, 5)
    # 예전 "다른 물건" (오른쪽 아래, x 635~880, y 1682~1757) — 왼쪽 배경을 좌우로 비춘다
    ox0 = 628
    src_x = np.clip(2 * ox0 - np.arange(W0), 0, W0 - 1)
    mirror_h = orig[:, src_x]
    m2 = pill_mask(636, 1682, 878, 1757, 6)
    a = (a * (1 - m1) + mirror_v * m1).astype(np.uint8)
    a = (a * (1 - m2) + mirror_h * m2).astype(np.uint8)

    img = Image.fromarray(a)
    d = ImageDraw.Draw(img, "RGBA")

    # ── 지금 배치: 아래에서부터 [다른 물건] 12dp 위 → [찾았어요] 16dp 위 → [이거 아니에요]
    W = img.width
    pill_h = int(44 * DP)
    pill_bottom = BOTTOM - int(12 * DP)
    pill_top = pill_bottom - pill_h
    f_other = ImageFont.truetype(FONT_SB, int(16 * DP * 0.95))
    tw = d.textlength("Other items", font=f_other)
    pill_w = int(tw + 2 * 20 * DP + 8 * DP)    # paddingStart/End 20dp + 배경 padding
    px0 = (W - pill_w) // 2
    d.rounded_rectangle([px0, pill_top, px0 + pill_w, pill_bottom], radius=int(22 * DP),
                        fill=(0, 0, 0, 136), outline=(255, 255, 255, 170), width=int(2 * DP))
    d.text((W / 2, (pill_top + pill_bottom) / 2), "Other items", font=f_other,
           fill=(255, 255, 255, 255), anchor="mm")

    found_bottom = pill_top - int(16 * DP)
    found_top = found_bottom - button.height
    img.paste(button, (bx0, found_top), bmask)

    f_not = ImageFont.truetype(FONT_SB, int(15 * DP * 0.95))
    not_cy = found_top - int(2 * DP) - int(24 * DP)
    d.text((W / 2, not_cy), "Not this one", font=f_not, fill=(255, 255, 255, 216), anchor="mm")

    return img.crop((0, TOP, W, BOTTOM))


# ── 찾았어요 화면 ────────────────────────────────────────────────────────────
def star(d: ImageDraw.ImageDraw, cx, cy, r, points, inner, fill):
    pts = []
    for i in range(points * 2):
        a = math.pi * i / points - math.pi / 2
        rr = r if i % 2 == 0 else r * inner
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    d.polygon(pts, fill=fill)


def firework(layer: Image.Image, cx, cy, radius, colors):
    """터지는 중인 불꽃 — 앱처럼 불똥마다 꼬리가 있고, 바깥쪽이 밝고, 살짝 처진다."""
    d = ImageDraw.Draw(layer, "RGBA")
    n = 56
    for i in range(n):
        a = 2 * math.pi * i / n + random.uniform(-0.05, 0.05)
        r = radius * random.uniform(0.8, 1.0)
        droop = (r / radius) ** 2 * radius * 0.12
        c = colors[1] if i % 3 == 0 else colors[0]
        steps = 6
        for s in range(steps):
            t0 = 0.55 + 0.45 * s / steps
            t1 = 0.55 + 0.45 * (s + 1) / steps
            p0 = (cx + math.cos(a) * r * t0, cy + math.sin(a) * r * t0 + droop * t0 * t0)
            p1 = (cx + math.cos(a) * r * t1, cy + math.sin(a) * r * t1 + droop * t1 * t1)
            d.line([p0, p1], fill=c + (int(40 + 200 * (s + 1) / steps),), width=2 + s // 2)
        ex, ey = cx + math.cos(a) * r, cy + math.sin(a) * r + droop
        d.ellipse([ex - 4, ey - 4, ex + 4, ey + 4], fill=c + (255,))


def found_screen(src: Path) -> Image.Image:
    a = np.asarray(Image.open(src).convert("RGB")).copy()
    ai = a.astype(int)
    yellow = (ai[:, :, 0] > 170) & (ai[:, :, 1] > 150) & (ai[:, :, 2] < 110) & \
             (ai[:, :, 0] - ai[:, :, 2] > 110)

    # 제목 (y 160~270) 노란 글자 → 흰 글자 + 파란 빛
    title = np.zeros(a.shape[:2], bool)
    title[160:275, 250:650] = True
    tmask = (yellow & title)
    tsoft = cv2.GaussianBlur(tmask.astype(np.float32), (0, 0), 0.8)

    # 사진 테두리 (둥근 사각형 선) 노랑 → 강조색. 선 근처 띠만.
    frame = np.zeros(a.shape[:2], bool)
    fx0, fy0, fx1, fy1 = 74, 328, 826, 1818
    band = 18
    frame[fy0 - band:fy1 + band, fx0 - band:fx1 + band] = True
    frame[fy0 + band:fy1 - band, fx0 + band:fx1 - band] = False
    fmask = yellow & frame
    fm = cv2.dilate(fmask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    # 테두리는 색만 바꾼다 (명도 유지)
    lum = a[fm].astype(float).mean(1, keepdims=True) / 156.0   # 노랑(255,214,0) 평균 밝기
    a[fm] = np.clip(np.array(ACCENT, float) * lum, 0, 255).astype(np.uint8)

    img = Image.fromarray(a)

    # 사진 뒤 숨쉬는 빛 — 사진 상자 바깥으로 번지게, 사진 위에는 안 올라가게
    cx, cy = 450, 1073
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i, r in enumerate(range(700, 0, -20)):
        alpha = int(90 * (1 - r / 700) ** 1.6)
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 190, 215, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    holdout = Image.new("L", img.size, 255)
    ImageDraw.Draw(holdout).rounded_rectangle([fx0, fy0, fx1, fy1], radius=40, fill=0)
    img = Image.composite(Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB"), img, holdout)

    # 제목: 흰 글자 + 파란 빛 (빛은 흐린 마스크를 파랗게)
    ta = np.asarray(img).copy()
    white = np.array((255, 255, 255), float)
    ta = (ta * (1 - tsoft[..., None]) + white * tsoft[..., None]).astype(np.uint8)
    img = Image.fromarray(ta)
    halo = Image.fromarray((tmask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(18))
    halo_rgba = Image.new("RGBA", img.size, ACCENT + (0,))
    halo_rgba.putalpha(halo.point(lambda v: min(255, int(v * 1.6))))
    under = Image.alpha_composite(img.convert("RGBA"), halo_rgba)
    # 빛 위에 다시 흰 글자
    img = Image.composite(img, under.convert("RGB"), Image.fromarray((tsoft * 255).astype(np.uint8)))

    fx = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(fx, "RGBA")

    # 불꽃 두 발 — 제목 양옆, 사진 테두리 위쪽 모서리 근처
    firework(fx, 140, 300, 100, ((255, 80, 120), (255, 200, 220)))
    firework(fx, 765, 280, 90, ((120, 200, 255), (230, 245, 255)))

    # 금색 별과 반짝이 — 사진 둘레
    gold = [(255, 236, 140), (255, 214, 0), (255, 255, 255)]
    for _ in range(22):
        ang = random.uniform(0, 2 * math.pi)
        rx, ry = 420 * random.uniform(0.9, 1.1), 780 * random.uniform(0.85, 1.05)
        x, y = cx + math.cos(ang) * rx, cy + math.sin(ang) * ry
        if not (40 < x < 860 and 300 < y < 1760):
            continue
        if random.random() < 0.45:
            star(d, x, y, random.uniform(10, 17), 5, 0.45, random.choice(gold) + (255,))
        else:
            star(d, x, y, random.uniform(12, 24), 4, 0.22, random.choice(gold) + (240,))

    # 색종이 비 — 위쪽에 조금 더
    colors = [(255, 214, 0), (255, 138, 0), (255, 45, 85), ACCENT, (140, 230, 140), (200, 140, 255)]
    for _ in range(46):
        x, y = random.uniform(0, 900), random.uniform(280, 1700)
        if fx0 < x < fx1 and fy0 < y < fy1 and random.random() < 0.8:
            continue
        w, h = random.uniform(12, 22), random.uniform(7, 13)
        rot = random.uniform(0, 180)
        piece = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        ImageDraw.Draw(piece).rectangle([20 - w / 2, 20 - h / 2, 20 + w / 2, 20 + h / 2],
                                        fill=random.choice(colors) + (255,))
        piece = piece.rotate(rot, resample=Image.BICUBIC)
        fx.alpha_composite(piece, (int(x - 20), int(y - 20)))

    img = Image.alpha_composite(img.convert("RGBA"), fx).convert("RGB")
    # 광고 줄 자리(사진 테두리 바깥)에 흐린 광고가 비친다. 축하 화면의 어두운 막처럼 누른다.
    # 테두리 선(강조색)과 합성한 효과는 건드리지 않는다.
    arr = np.asarray(img).astype(float)
    low = arr[1776:]
    stroke = np.abs(low - np.array(ACCENT, float)).sum(2) < 120
    effects = np.asarray(fx.split()[3])[1776:] > 40
    keep = stroke | effects
    low[~keep] *= 0.35
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    # 이 화면은 사진 테두리가 광고 줄 자리까지 내려오므로 테두리 아래까지 남긴다 (900x1760)
    return img.crop((0, TOP, img.width, FOUND_BOTTOM))


def main() -> None:
    search, found = Path(sys.argv[1]), Path(sys.argv[2])
    OUT.mkdir(parents=True, exist_ok=True)
    for name, im in (("screenshot-1-found.png", found_screen(found)),
                     ("screenshot-2-search.png", search_screen(search))):
        p = OUT / name
        im.save(p)
        print(p, im.size)


if __name__ == "__main__":
    main()
