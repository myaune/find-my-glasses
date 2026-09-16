"""YOLO-World dynamic ONNX 를 FP16 으로 변환한다 (입출력은 FP32 유지).

ultralytics 의 half=True 익스포트는 GPU 가 있어야 해서 CPU 로는 안 된다.
그래서 FP32 ONNX 를 onnxconverter-common 으로 변환한다. Grounding DINO 때 만든
타입 수리 패스(onnx_fp16.repair_mixed_types_iter)를 그대로 쓴다.

입출력을 FP32 로 유지하는 이유는 Kotlin 에서 FloatBuffer 로 그대로 넘기기 위해서다.

ARM CPU 에는 FP16 연산기가 없어 오히려 느려질 수 있다. 크기(대략 절반)와 속도를
실기기에서 같이 보고 정한다.

    uv run python scripts/yolo_fp16.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnxconverter_common import float16

sys.path.insert(0, str(Path(__file__).resolve().parent))

from onnx_fp16 import repair_mixed_types_iter  # noqa: E402

MB = 1024 ** 2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path,
                    default=Path("../android/app/src/main/assets/yolo-world-s-dyn.onnx"))
    ap.add_argument("--dst", type=Path,
                    default=Path("../android/app/src/main/assets/yolo-world-s-dyn-fp16.onnx"))
    args = ap.parse_args()

    m = onnx.load(str(args.src))
    # GDINO 는 커서 형상 추론을 껐지만 YOLO 는 작다. 켜두면 변환기가 차단 연산(Resize 등)
    # 주변에 끼운 Cast 의 타입 선언까지 맞춰준다. 끄면 value_info 가 원래 타입으로
    # 남아 "Resize_output_cast0 출력이 float16 이어야 한다" 로 로드가 실패했다.
    m16 = float16.convert_float_to_float16(m, keep_io_types=True, disable_shape_infer=False)
    # 그래도 남은 낡은 타입 선언은 지운다. ORT 가 로드할 때 스스로 추론한다.
    del m16.graph.value_info[:]
    n = repair_mixed_types_iter(m16)
    if n:
        print(f"혼합 타입 {n}곳 수리")
    onnx.save(m16, str(args.dst))

    print(f"FP32 {args.src.stat().st_size / MB:.1f} MB → FP16 {args.dst.stat().st_size / MB:.1f} MB")

    so = ort.SessionOptions()
    so.log_severity_level = 3
    s32 = ort.InferenceSession(str(args.src), so, providers=["CPUExecutionProvider"])
    s16 = ort.InferenceSession(str(args.dst), so, providers=["CPUExecutionProvider"])

    rng = np.random.default_rng(0)
    for size in (416, 640):
        x = rng.random((1, 3, size, size), dtype=np.float32)
        a = s32.run(None, {s32.get_inputs()[0].name: x})[0]
        b = s16.run(None, {s16.get_inputs()[0].name: x})[0]
        # 채널 4.. 가 클래스 점수. 검출에 쓰는 값이 얼마나 달라지는지 본다.
        sa, sb = a[:, 4:, :], b[:, 4:, :]
        print(f"  {size}px  점수 최대차 {np.abs(sa - sb).max():.4f}  "
              f"박스 최대차 {np.abs(a[:, :4, :] - b[:, :4, :]).max():.2f}px")


if __name__ == "__main__":
    main()
