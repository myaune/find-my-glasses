"""모델 후보를 폰에 올리기 전에 데스크탑에서 탈락시키는 관문.

이 스크립트가 있었어야 했다. Grounding DINO Tiny 는 데스크탑 CPU 에서 한
프레임에 3.1초였고, 그 숫자만으로 폰에서는 수십 초가 예측됐다. 실측 35초.
안드로이드 SDK 를 깔기 전에 알 수 있었다.

기준
    폰 목표 500ms.
    보급형 ARM(Cortex-A73 x4) 은 데스크탑 8코어 x86 대비 대략 1/8 ~ 1/15.
    따라서 데스크탑 CPU 에서 60ms 를 넘으면 폰에서 500ms 가 불가능하다.

    GDINO Tiny: 3100ms → 52배 초과. 즉시 탈락.

CPU 로만 잰다. GPU 수치는 폰과 아무 관계가 없다. 3070 에서 289ms 가 나온 게
판단을 흐렸다.

    uv run python scripts/latency_gate.py --model yolo-world
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.config import NEGATIVE_PROMPTS  # noqa: E402

# 폰 500ms 를 맞추려면 데스크탑 CPU 에서 이 값 이하여야 한다.
GATE_MS = 60.0
# 데스크탑 8코어 x86 → 보급형 ARM 4x A73 환산 배수 (경험적 범위)
ARM_FACTOR_LOW, ARM_FACTOR_HIGH = 8, 15


def bench(fn, warmup: int = 1, runs: int = 5) -> list[float]:
    for _ in range(warmup):
        fn()
    out = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000.0)
    return out


def load_image(data_dir: Path) -> Image.Image:
    imgs = sorted((data_dir / "images").glob("*.jpg"))
    if not imgs:
        raise SystemExit(f"사진이 없습니다: {data_dir / 'images'}")
    return Image.open(imgs[0]).convert("RGB")


def run_yolo_world(img: Image.Image, size: int, weights: str):
    from ultralytics import YOLOWorld

    model = YOLOWorld(weights)
    # set_classes 는 CLIP 텍스트 인코더를 필요로 하는데, 레이턴시 측정에는
    # 무관하다. 텍스트 임베딩은 프레임마다 돌지 않고 어휘를 바꿀 때 한 번만
    # 계산되며, 배포 시에는 빌드 타임에 구워넣는다 (기획서 6절).
    classes = ["eyeglasses"] + [n.lower() for n in NEGATIVE_PROMPTS]
    try:
        model.set_classes(classes)
        print(f"  어휘 설정: {classes}")
    except ModuleNotFoundError as e:
        print(f"  어휘 설정 건너뜀 ({e.name} 없음) — 레이턴시에는 영향 없음")
    # CPU 로 고정. GPU 수치는 폰과 관계가 없다.
    model.to("cpu")

    arr = np.asarray(img)

    def once():
        model.predict(arr, imgsz=size, device="cpu", verbose=False)

    n_params = sum(p.numel() for p in model.model.parameters())
    return once, n_params


def run_onnx(img: Image.Image, size: int, onnx_path: Path):
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.log_severity_level = 3
    sess = ort.InferenceSession(str(onnx_path), so, providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0]
    fp16 = "float16" in inp.type

    s = size / max(img.width, img.height)
    nw, nh = max(1, round(img.width * s)), max(1, round(img.height * s))
    canvas = Image.new("RGB", (size, size), (0, 0, 0))
    canvas.paste(img.resize((nw, nh), Image.BILINEAR),
                 ((size - nw) // 2, (size - nh) // 2))
    x = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
    mean = np.array([0.485, 0.456, 0.406], np.float32).reshape(1, 3, 1, 1)
    std = np.array([0.229, 0.224, 0.225], np.float32).reshape(1, 3, 1, 1)
    x = (x - mean) / std
    x = x.astype(np.float16 if fp16 else np.float32)

    def once():
        sess.run(None, {inp.name: x})

    return once, None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="yolo-world")
    ap.add_argument("--weights", default="yolov8s-worldv2.pt")
    ap.add_argument("--onnx", type=Path)
    ap.add_argument("--size", type=int, default=640)
    ap.add_argument("--data", type=Path, default=Path("../data"))
    ap.add_argument("--runs", type=int, default=5)
    args = ap.parse_args()

    img = load_image(args.data)
    print(f"입력 사진 {img.width}x{img.height} → imgsz {args.size}")

    if args.onnx:
        label = f"ONNX {args.onnx.name}"
        once, n_params = run_onnx(img, args.size, args.onnx)
    elif args.model == "yolo-world":
        label = f"YOLO-World {args.weights}"
        once, n_params = run_yolo_world(img, args.size, args.weights)
    else:
        raise SystemExit(f"모르는 모델: {args.model}")

    times = bench(once, runs=args.runs)
    med = statistics.median(times)

    print(f"\n{label}")
    if n_params:
        print(f"  파라미터 {n_params / 1e6:.1f}M  (fp16 ≈ {n_params * 2 / 1024**2:.0f}MB)")
    print(f"  데스크탑 CPU  중앙값 {med:.0f}ms  "
          f"(최소 {min(times):.0f} / 최대 {max(times):.0f}, n={len(times)})")

    lo = med * ARM_FACTOR_LOW
    hi = med * ARM_FACTOR_HIGH
    print(f"  SD685 추정    {lo:.0f} ~ {hi:.0f}ms  (환산 {ARM_FACTOR_LOW}~{ARM_FACTOR_HIGH}배)")

    print(f"\n  관문 {GATE_MS:.0f}ms → ", end="")
    if med <= GATE_MS:
        print("통과. 폰 테스트로 진행할 가치가 있다")
    else:
        print(f"탈락. {med / GATE_MS:.0f}배 초과")
        print("  폰에 올려볼 이유가 없다. 여기서 멈추고 다른 후보를 본다.")

    print("\n주의: 환산 배수는 경험적 범위다. 관문을 통과한 후보만 폰에서 실측한다.")


if __name__ == "__main__":
    main()
