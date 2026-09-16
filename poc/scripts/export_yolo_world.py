"""YOLO-World 를 어휘가 구워진 ONNX 로 내보낸다.

set_classes 를 부르면 CLIP 텍스트 임베딩이 검출 헤드에 반영된다. 그 상태로
익스포트하면 런타임에 텍스트 인코더가 필요 없다 — 기획서 6절이 Grounding
DINO 에 대해 하려던 것과 같은 얘기인데, 이쪽은 CNN 이라 원래 가볍다.

라이선스: 모델 GPL-3.0, ultralytics AGPL-3.0. 앱 소스를 공개하는 전제로
채택한다 (기획서 13절의 재검토 조건).

    uv run python scripts/export_yolo_world.py --imgsz 416
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.config import NEGATIVE_PROMPTS  # noqa: E402

MB = 1024 ** 2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="yolov8s-worldv2.pt")
    ap.add_argument("--positive", default="eyeglasses")
    ap.add_argument("--imgsz", type=int, default=416)
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--half", action="store_true",
                    help="fp16 으로 내보낸다. ARM CPU 는 fp16 연산기가 없어 오히려 "
                         "느릴 수 있으므로 기본은 fp32 다.")
    ap.add_argument("--out", type=Path, default=Path("../runs/yolo-onnx"))
    args = ap.parse_args()

    from ultralytics import YOLOWorld

    classes = [args.positive] + [n.lower() for n in NEGATIVE_PROMPTS]
    print(f"어휘 {len(classes)}개: {classes}")

    model = YOLOWorld(args.weights)
    model.set_classes(classes)

    n_params = sum(p.numel() for p in model.model.parameters())
    print(f"파라미터 {n_params / 1e6:.1f}M")

    print(f"\nONNX 익스포트 (imgsz {args.imgsz}, opset {args.opset}, "
          f"{'fp16' if args.half else 'fp32'}) …")
    path = model.export(
        format="onnx",
        imgsz=args.imgsz,
        opset=args.opset,
        half=args.half,
        simplify=True,
        dynamic=False,
        device="cpu",
    )

    args.out.mkdir(parents=True, exist_ok=True)
    tag = f"{args.imgsz}-{'fp16' if args.half else 'fp32'}"
    dst = args.out / f"yolo-world-s-{args.positive}-{tag}.onnx"
    shutil.copy2(path, dst)

    size = dst.stat().st_size
    print(f"\n{dst}")
    print(f"  {size / MB:.1f} MB")
    print(f"  100MB 목표 → {'통과' if size / MB <= 100 else '초과'}")

    # 출력 형태와 클래스 순서를 Android 쪽에 알려야 한다.
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.log_severity_level = 3
    sess = ort.InferenceSession(str(dst), so, providers=["CPUExecutionProvider"])
    print("\n입력")
    for i in sess.get_inputs():
        print(f"  {i.name} {i.shape} {i.type}")
    print("출력")
    for o in sess.get_outputs():
        print(f"  {o.name} {o.shape} {o.type}")

    print("\n클래스 순서 (출력 채널 4..4+nc 에 대응)")
    for i, c in enumerate(classes):
        print(f"  {i}: {c}{'   ← 양성' if i == 0 else ''}")

    print("\n주의: ultralytics 의 ONNX 출력은 [1, 4+nc, N] 이고 좌표는 xywh "
          "(입력 픽셀 기준, 정규화 아님). NMS 는 포함되지 않는다.")


if __name__ == "__main__":
    main()
