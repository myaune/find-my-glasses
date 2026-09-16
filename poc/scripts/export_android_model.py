"""앱에 넣는 YOLO-World s ONNX 를 만든다 (입력 크기 dynamic, 어휘가 구워짐).

앱은 입력 해상도를 런타임에 바꾸므로(416/512/640) dynamic 으로 내보낸다.
어휘 순서는 android ModelCatalog.CLASSES 와 반드시 같아야 한다. 뒤에 추가만 하고
기존 순서는 바꾸지 않는다.

학습이 아니다. set_classes 는 CLIP 텍스트 임베딩을 헤드에 넣을 뿐이다.

어휘를 바꾸면 기존 모델과 안경 점수를 비교한다. 클래스마다 점수를 따로 내긴 하지만
YOLO-World 는 텍스트 임베딩을 넥(RepVL-PAN)에도 섞으므로 어휘가 바뀌면 안경 점수도
조금 움직인다. "car key" 를 추가했을 때 사진 19장 @416 에서 평균 0.010, 최대 0.046
차이였고 안경 없는 사진 2장은 0.003 이하로 그대로였다.

    uv run python scripts/export_android_model.py --compare <기존 모델.onnx>
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

MB = 1024 ** 2

# android ModelCatalog.CLASSES 와 같은 순서
CLASSES = [
    "a pair of eyeglasses",  # 0 — 기본 대상
    "keys",                  # 1 — 부가 기능: 열쇠
    "phone",                 # 2 — 부가 기능: 휴대폰
    "scissors",
    "pen",
    "remote control",        # 5 — 부가 기능: 리모컨
    "cup",
    "car key",               # 7 — 부가 기능: 열쇠 (차 스마트키). 2026-09-13 추가
]


def letterbox(img: Image.Image, size: int) -> np.ndarray:
    w, h = img.size
    s = size / max(w, h)
    nw, nh = round(w * s), round(h * s)
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    canvas.paste(img.resize((nw, nh), Image.BILINEAR), ((size - nw) // 2, (size - nh) // 2))
    x = np.asarray(canvas, dtype=np.float32) / 255.0
    return x.transpose(2, 0, 1)[None]


def top_scores(path: Path, x: np.ndarray, n: int) -> np.ndarray:
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.log_severity_level = 3
    sess = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0]  # [1, 4+nc, N]
    return out[0, 4:4 + n].max(axis=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="yolov8s-worldv2.pt")
    ap.add_argument("--out", type=Path, default=Path("../runs/yolo-onnx/yolo-world-s-v2.onnx"))
    ap.add_argument("--compare", type=Path, help="기존 모델. 안경 점수를 비교한다")
    ap.add_argument("--image", type=Path, default=Path("../data/images/1789124976070.jpg"))
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    from ultralytics import YOLOWorld

    print(f"어휘 {len(CLASSES)}개")
    for i, c in enumerate(CLASSES):
        print(f"  {i}: {c}")

    model = YOLOWorld(args.weights)
    model.set_classes(CLASSES)
    p = model.export(format="onnx", imgsz=640, opset=17, dynamic=True, simplify=True, device="cpu")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, args.out)
    print(f"\n{args.out}  {args.out.stat().st_size / MB:.1f} MB")

    if args.image.exists():
        x = letterbox(Image.open(args.image).convert("RGB"), args.imgsz)
        new = top_scores(args.out, x, len(CLASSES))
        print(f"\n기준 사진 {args.image.name} @{args.imgsz}")
        for i, c in enumerate(CLASSES):
            print(f"  {c:22s} {new[i]:.4f}")
        if args.compare and args.compare.exists():
            old_n = len(CLASSES) - 1
            old = top_scores(args.compare, x, old_n)
            diff = float(np.abs(old - new[:old_n]).max())
            print(f"\n기존 모델과 최대 점수차 {diff:.6f} (기존 클래스 {old_n}개)")
            print(f"  안경 기존 {old[0]:.4f} / 새 {new[0]:.4f}")


if __name__ == "__main__":
    main()
