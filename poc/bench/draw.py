"""검출 결과를 이미지에 그려 눈으로 확인할 수 있게 한다.

Phase 0 1단계에는 정답 박스가 없다. 박스가 실제로 안경 위에 있는지는
사람이 봐야 하므로, 렌더링이 판정의 일부다.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .detectors.base import Det

POS_COLOR = (255, 60, 60)
NEG_COLOR = (90, 140, 255)


def _font(size: int = 16):
    for name in ("malgun.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def annotate(image: Image.Image, dets: list[Det], title: str = "") -> Image.Image:
    out = image.copy().convert("RGB")
    d = ImageDraw.Draw(out)
    f = _font(max(14, out.width // 60))

    for det in sorted(dets, key=lambda x: x.score):
        color = POS_COLOR if det.is_positive else NEG_COLOR
        w = 4 if det.is_positive else 2
        d.rectangle(det.box, outline=color, width=w)
        tag = f"{det.label} {det.score:.2f}"
        x, y = det.box[0], max(0, det.box[1] - f.size - 4)
        tb = d.textbbox((x, y), tag, font=f)
        d.rectangle(tb, fill=color)
        d.text((x, y), tag, fill=(255, 255, 255), font=f)

    if title:
        tb = d.textbbox((4, 4), title, font=f)
        d.rectangle(tb, fill=(0, 0, 0))
        d.text((4, 4), title, fill=(255, 255, 0), font=f)
    return out


def save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, quality=90)
