"""스토어 스크린샷 (노랑 테마) — 1080x1920 두 장.

아이콘과 같은 노랑 배경 + 먹색 글자. 배경에 아이콘의 안경을 크게 옅게 깔아
왼쪽 알은 1장, 오른쪽 알은 2장 뒤에 오게 한다 (나란히 보면 안경 하나로 이어진다).
문구는 짧게, 스토어 설명글에서 가져온다 (첫 문장 / 폭죽 문장).

    uv run python scripts/render_store_yellow.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from render_store_marketing import REL, SS, phone, place, screen

W, H = 1080, 1920
YELLOW = (255, 217, 90)
INK = (43, 43, 48)
FB = r"C:\Windows\Fonts\segoeuib.ttf"

TILES = [
    # (화면, 문구, 폰 기울기)
    ("screenshot-2-search.png", ("Find your glasses", "without your glasses."), -4.0),
    ("screenshot-1-found.png", ("Your camera app", "won’t set off fireworks."), 4.0),
]


def glasses(canvas: Image.Image):
    """아이콘의 안경 (108 격자 좌표) 을 알 가운데가 두 장의 가운데에 오게 크게 그린다."""
    k = W * SS / 30.0                         # 두 알 가운데 사이 30 단위 = 1080px
    ox = W * SS / 2 - 39 * k                  # 왼쪽 알 가운데 (x=39) → 1장 가운데
    oy = 1180 * SS - 54.5 * k                 # 알 가운데 높이 (y=54.5)
    stroke = int(3.2 * k * 0.55)
    col = INK + (38,)
    lay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)

    def P(x, y):
        return ox + x * k, oy + y * k

    for x0 in (27, 57):
        d.rounded_rectangle([*P(x0, 45.5), *P(x0 + 24, 63.5)], radius=8 * k, outline=col, width=stroke)
    # 브릿지 (2차 곡선)
    pts = []
    for i in range(25):
        t = i / 24
        x = (1 - t) ** 2 * 51 + 2 * (1 - t) * t * 54 + t ** 2 * 57
        y = (1 - t) ** 2 * 51.5 + 2 * (1 - t) * t * 47.5 + t ** 2 * 51.5
        pts.append(P(x, y))
    d.line(pts, fill=col, width=stroke, joint="curve")
    # 다리
    d.line([P(27, 50), P(20, 47.5)], fill=col, width=stroke)
    d.line([P(81, 50), P(88, 47.5)], fill=col, width=stroke)
    canvas.alpha_composite(lay)


def main() -> None:
    PW, PH = W * 2 * SS, H * SS
    canvas = Image.new("RGBA", (PW, PH), YELLOW + (255,))
    glasses(canvas)

    f = ImageFont.truetype(FB, 80 * SS)
    d = ImageDraw.Draw(canvas)
    for i, (name, (l1, l2), ang) in enumerate(TILES):
        cx = (i * W + W // 2) * SS
        place(canvas, phone(screen(name), 1300 * SS), cx, 1230 * SS, ang)
        d.text((cx, 175 * SS), l1, font=f, fill=INK, anchor="mm")
        d.text((cx, 280 * SS), l2, font=f, fill=INK, anchor="mm")

    full = canvas.convert("RGB").resize((W * 2, H), Image.LANCZOS)
    full.save(REL / "store-yellow-spread.png")
    for i in range(2):
        p = REL / f"store-yellow-{i + 1}.png"
        full.crop((i * W, 0, (i + 1) * W, H)).save(p)
        print(p)


if __name__ == "__main__":
    main()
