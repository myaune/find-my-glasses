"""스모크 테스트 — 실제 안경 사진 없이 파이프라인이 도는지 확인한다.

특히 OWLv2 의 정사각 패딩 좌표 보정이 맞는지를, 위치를 아는 공개 테스트
이미지(COCO val2017 고양이 사진)로 검증한다. 박스가 엉뚱한 곳에 찍히는 것은
OWLv2 에서 흔한 함정이라 실제 데이터를 받기 전에 잡아야 한다.

    uv run python scripts/smoke.py
"""
from __future__ import annotations

import io
import os
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.detectors import build  # noqa: E402
from bench.draw import annotate, save  # noqa: E402

URL = "http://images.cocodataset.org/val2017/000000039769.jpg"
OUT = Path(os.environ.get("SMOKE_OUT", Path(__file__).resolve().parents[2] / "runs" / "smoke"))


def load_image() -> Image.Image:
    cache = OUT / "cats.jpg"
    if cache.exists():
        return Image.open(cache).convert("RGB")
    with urllib.request.urlopen(URL, timeout=60) as resp:
        data = resp.read()
    img = Image.open(io.BytesIO(data)).convert("RGB")
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(cache)
    return img


def main() -> None:
    img = load_image()
    print(f"테스트 이미지 {img.width}x{img.height}")
    # 이 사진은 소파 위에 고양이 두 마리 + 리모컨 두 개다.
    # 고양이는 화면 좌우로 나뉘어 크게 잡히므로 박스 위치가 맞는지 눈으로 검증된다.
    positives = ["cat"]
    negatives = ["remote control", "couch", "blanket"]

    ok = True
    for key in ("grounding-dino-tiny", "owlv2-base"):
        print(f"\n=== {key} ===")
        det = build(key)
        print(f"  파라미터 {det.param_bytes() / 1024**2:.1f} MB (fp32)")

        dets = det.detect(img, positives, negatives, 0.15)
        dets.sort(key=lambda d: -d.score)
        for d in dets[:8]:
            cx = (d.box[0] + d.box[2]) / 2 / img.width
            cy = (d.box[1] + d.box[3]) / 2 / img.height
            print(f"  {d.label:16s} {d.score:.3f}  center=({cx:.2f}, {cy:.2f})  "
                  f"box={[round(v) for v in d.box]}")
        save(annotate(img, dets, f"{key} | smoke"), OUT / f"{key}.jpg")

        cats = [d for d in dets if d.is_positive or d.label.strip().lower() == "cat"]
        if not cats:
            print("  !! 고양이를 못 잡았습니다 — 파이프라인 이상")
            ok = False
        else:
            # 박스가 이미지 경계 안에 있고 면적이 말이 되는지
            for d in cats[:2]:
                x1, y1, x2, y2 = d.box
                area = (x2 - x1) * (y2 - y1) / (img.width * img.height)
                inside = 0 <= x1 < x2 <= img.width and 0 <= y1 < y2 <= img.height
                print(f"  좌표검증 inside={inside} area_ratio={area:.2f}")
                if not inside or not (0.02 < area < 0.95):
                    print("  !! 박스 좌표가 이상합니다")
                    ok = False

        if hasattr(det, "detect_embed_ensemble"):
            e = det.detect_embed_ensemble(img, ["cat", "a photo of a cat", "kitten"],
                                          negatives, 0.15)
            e.sort(key=lambda d: -d.score)
            print(f"  임베딩 앙상블: {len(e)}개, top="
                  f"{[(d.label[:20], round(d.score, 3)) for d in e[:3]]}")
            save(annotate(img, e, f"{key} | embed ensemble"), OUT / f"{key}_ensemble.jpg")
            if not e:
                print("  !! 임베딩 앙상블이 아무것도 못 냈습니다")
                ok = False

        del det

    print(f"\n렌더링 → {OUT}")
    print("결과:", "OK" if ok else "문제 있음")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
