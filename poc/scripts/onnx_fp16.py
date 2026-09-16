"""Phase 0b — ONNX 를 FP16 으로 변환하고 수치가 유지되는지 확인한다.

기획서 11절: FP32 로 측정한 뒤 배포 포맷에서 recall 이 반토막 나는 것이
고전적 함정이다. 여기서는 먼저 "출력 텐서 자체가 얼마나 달라지는가" 를 본다.
검출 단위 비교는 bench.detectors.gdino_onnx 로 파이프라인을 다시 돌려서 한다.

    uv run python scripts/onnx_fp16.py
"""
from __future__ import annotations

import argparse
import gzip
import shutil
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnxconverter_common import float16

MB = 1024 ** 2


COMPARE_OPS = {"Equal", "Greater", "GreaterOrEqual", "Less", "LessOrEqual", "Where"}

# 입력 타입을 그대로 물려주는 연산들. 타입 전파에만 쓴다.
PASSTHROUGH_OPS = {
    "Add", "Sub", "Mul", "Div", "Neg", "Abs", "Sqrt", "Pow", "Exp", "Log",
    "Unsqueeze", "Squeeze", "Reshape", "Transpose", "Slice", "Concat", "Split",
    "Gather", "GatherElements", "GatherND", "Expand", "Tile", "Identity",
    "Flatten", "Pad", "Clip", "Min", "Max", "Where", "CumSum", "ScatterND",
    "ReduceSum", "ReduceMean", "ReduceMax", "ReduceMin", "ReduceProd",
    "MatMul", "Gemm", "Conv", "Relu", "Sigmoid", "Softmax", "Erf", "Tanh",
    "LayerNormalization", "InstanceNormalization", "Resize", "GridSample",
    "Einsum", "Mod", "Round", "Floor", "Ceil", "Sin", "Cos",
}
BOOL_OUT_OPS = {"Equal", "Greater", "GreaterOrEqual", "Less", "LessOrEqual",
                "Not", "And", "Or", "Xor", "IsNaN", "IsInf"}

# 입력들의 타입이 서로 같아야 하는 연산. 여기서 float/float16 이 섞이면 로드가
# 실패하므로 fp16 으로 통일한다.
REPAIR_OPS = BOOL_OUT_OPS | {
    "Where", "Add", "Sub", "Mul", "Div", "Pow", "Mod", "Min", "Max",
    "Concat", "MatMul", "Gemm", "Einsum", "GridSample", "ScatterND",
    "CumSum", "Clip", "PRelu", "BiasGelu",
}


def infer_value_types(graph) -> dict[str, int]:
    """그래프를 위상 순서대로 훑으며 값의 elem_type 을 전파한다.

    onnx.shape_inference 가 채우지 못하는 값이 있어 직접 한다. Constant 노드는
    initializer 가 아니라 attribute 에 타입이 들어 있어서 따로 읽어야 한다.
    """
    from onnx import TensorProto

    INT_LIKE = {TensorProto.INT64, TensorProto.INT32, TensorProto.BOOL}
    t: dict[str, int] = {}

    for init in graph.initializer:
        t[init.name] = init.data_type
    for vi in list(graph.input) + list(graph.value_info) + list(graph.output):
        if vi.type.HasField("tensor_type") and vi.type.tensor_type.elem_type:
            t[vi.name] = vi.type.tensor_type.elem_type

    for n in graph.node:
        if n.op_type in ("Constant", "ConstantOfShape"):
            for a in n.attribute:
                if a.name == "value":
                    t[n.output[0]] = a.t.data_type
                elif a.name == "value_float":
                    t[n.output[0]] = TensorProto.FLOAT
                elif a.name in ("value_int", "value_ints"):
                    t[n.output[0]] = TensorProto.INT64
        elif n.op_type == "Cast":
            for a in n.attribute:
                if a.name == "to":
                    t[n.output[0]] = a.i
        elif n.op_type in ("Shape", "Size", "NonZero", "ArgMax", "ArgMin"):
            t[n.output[0]] = TensorProto.INT64
        elif n.op_type in BOOL_OUT_OPS:
            t[n.output[0]] = TensorProto.BOOL
        elif n.op_type in PASSTHROUGH_OPS:
            ins = n.input[1:] if n.op_type == "Where" else n.input
            picked = None
            for inp in ins:
                ty = t.get(inp)
                if ty is not None and ty not in INT_LIKE:
                    picked = ty
                    break
            if picked is None:
                for inp in ins:
                    if t.get(inp) is not None:
                        picked = t[inp]
                        break
            if picked is not None:
                for o in n.output:
                    t[o] = picked
    return t


def repair_mixed_types(model: onnx.ModelProto, name_offset: int = 0) -> int:
    """float / float16 이 섞인 비교 노드에 Cast 를 끼워 넣는다.

    float16 변환기가 비교 노드의 한쪽 입력(초기화 상수)만 fp16 으로 바꿔서
    "Type parameter (T) bound to different types" 로 로드가 실패하는 경우가
    있다. op_block_list 로도 막히지 않아 직접 고친다.
    """
    from onnx import TensorProto, helper

    # 주의: onnx.shape_inference.infer_shapes 는 새 모델을 반환한다. 그 결과에
    # 노드를 끼워 넣으면 원본은 그대로라 수정이 저장되지 않는다. 타입은
    # infer_value_types 가 직접 전파하므로 여기서 부르지 않는다.
    g = model.graph
    tmap = infer_value_types(g)

    fixed = 0
    i = 0
    while i < len(g.node):
        node = g.node[i]

        if node.op_type not in REPAIR_OPS:
            i += 1
            continue
        # 전부 fp16 으로 통일한다. fp32 로 맞추면 그 출력이 fp32 섬이 되어
        # 하류에서 다시 충돌한다.
        target = TensorProto.FLOAT16
        skip_first = node.op_type == "Where"  # 첫 입력은 bool 조건

        data_inputs = [n for j, n in enumerate(node.input) if not (skip_first and j == 0)]
        types = {tmap.get(n) for n in data_inputs}
        if not (TensorProto.FLOAT in types and TensorProto.FLOAT16 in types):
            i += 1
            continue

        for j, name in enumerate(node.input):
            if skip_first and j == 0:
                continue
            ty = tmap.get(name)
            if ty not in (TensorProto.FLOAT, TensorProto.FLOAT16) or ty == target:
                continue
            uid = name_offset + fixed
            out = f"{name}_repaircast_{uid}"
            g.node.insert(i, helper.make_node(
                "Cast", [name], [out], to=target, name=f"Cast_repair_{uid}"))
            node.input[j] = out
            tmap[out] = target
            fixed += 1
            i += 1
        i += 1
    return fixed


def repair_mixed_types_iter(model: onnx.ModelProto, max_rounds: int = 8) -> int:
    """Cast 를 끼우면 타입이 바뀌어 새 충돌이 생길 수 있다. 안정될 때까지 반복."""
    total = 0
    for r in range(max_rounds):
        n = repair_mixed_types(model, name_offset=total)
        total += n
        print(f"  라운드 {r + 1}: {n}곳 수정")
        if n == 0:
            break
    return total


def gz_size(path: Path) -> int:
    """AAB 다운로드 크기 추정용. 가중치는 엔트로피가 높아 잘 안 줄어든다."""
    tmp = path.with_suffix(path.suffix + ".gz")
    with path.open("rb") as f_in, gzip.open(tmp, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out, length=8 << 20)
    n = tmp.stat().st_size
    tmp.unlink()
    return n


def run(path: Path, x: np.ndarray) -> list[np.ndarray]:
    so = ort.SessionOptions()
    so.log_severity_level = 3
    sess = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    want = sess.get_inputs()[0].type
    xi = x.astype(np.float16) if "float16" in want else x.astype(np.float32)
    return sess.run(None, {name: xi})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=Path("../runs/0b"))
    ap.add_argument("--name", default="gdino-tiny-eyeglasses")
    ap.add_argument("--height", type=int, default=800)
    ap.add_argument("--width", type=int, default=800)
    ap.add_argument("--keep-io-fp32", action="store_true",
                    help="입출력만 fp32 로 유지한다. 내부 연산은 그대로 fp16. "
                         "Android/Kotlin 에서 FloatBuffer 로 넘길 수 있어 간단해진다.")
    args = ap.parse_args()

    fp32 = args.run / f"{args.name}-fp32.onnx"
    suffix = "fp16-iofp32" if args.keep_io_fp32 else "fp16"
    fp16 = args.run / f"{args.name}-{suffix}.onnx"
    if not fp32.exists():
        raise SystemExit(f"없습니다: {fp32}. 먼저 export_onnx.py 를 돌려주세요.")

    print("FP16 변환 …")
    t0 = time.perf_counter()
    m = onnx.load(str(fp32))
    # keep_io_types=False 로 입력까지 fp16 으로 둔다. 앱에서 전처리 결과를
    # 그대로 fp16 으로 넘기면 변환 노드가 붙지 않는다.
    # op_block_list 로 특정 연산을 fp32 로 남기면, 그 출력이 fp32 섬이 되어
    # 하류 산술 연산마다 타입이 충돌한다(Equal → Where → Add 로 번졌다).
    # 기본 블록 리스트만 쓰고, 남는 불일치는 repair 가 fp16 으로 통일한다.
    m16 = float16.convert_float_to_float16(
        m, keep_io_types=args.keep_io_fp32, disable_shape_infer=True)
    n_fixed = repair_mixed_types_iter(m16)
    if n_fixed:
        print(f"혼합 타입 비교 노드 {n_fixed}곳에 Cast 삽입")
    onnx.save(m16, str(fp16))
    print(f"완료 {time.perf_counter() - t0:.1f}s")

    s32, s16 = fp32.stat().st_size, fp16.stat().st_size
    print(f"\n{'':16s} {'파일':>10s} {'gzip':>10s}")
    for label, p, s in (("FP32", fp32, s32), ("FP16", fp16, s16)):
        g = gz_size(p)
        print(f"{label:16s} {s / MB:9.1f}M {g / MB:9.1f}M")

    print(f"\n100MB 목표 대비 FP16: {s16 / MB:.1f} MB "
          f"→ {'통과' if s16 / MB <= 100 else '초과'}")
    print(f"150MB 목표 대비 FP16: {s16 / MB:.1f} MB "
          f"→ {'통과' if s16 / MB <= 150 else '초과'}")

    # 같은 입력에 대해 출력이 얼마나 달라지는가
    rng = np.random.default_rng(0)
    x = rng.standard_normal((1, 3, args.height, args.width), dtype=np.float32)
    print("\n출력 비교 (같은 입력) …")
    o32 = run(fp32, x)
    o16 = run(fp16, x)
    names = ["logits", "pred_boxes"]
    for n, a, b in zip(names, o32, o16):
        a = a.astype(np.float32)
        b = b.astype(np.float32)
        diff = np.abs(a - b)
        denom = np.abs(a).max() or 1.0
        print(f"  {n:12s} shape{a.shape}  최대차 {diff.max():.5f}  "
              f"평균차 {diff.mean():.6f}  상대 최대차 {diff.max() / denom:.5f}")

    # 검출에 실제로 쓰이는 값은 sigmoid(logits) 의 최대값이다
    p32 = 1.0 / (1.0 + np.exp(-o32[0].astype(np.float32)))
    p16 = 1.0 / (1.0 + np.exp(-o16[0].astype(np.float32)))
    s32m = p32.max(axis=-1).ravel()
    s16m = p16.max(axis=-1).ravel()
    order = np.argsort(-s32m)[:20]
    print(f"\n  상위 20개 쿼리 점수 최대차 {np.abs(s32m[order] - s16m[order]).max():.5f}")
    print(f"  전체 쿼리 점수 최대차     {np.abs(s32m - s16m).max():.5f}")

    print("\n주의: 무작위 입력에 대한 수치 비교다. 실제 사진에서 검출이")
    print("      유지되는지는 파이프라인을 다시 돌려 확인해야 한다.")


if __name__ == "__main__":
    main()
