import sys
from pathlib import Path

import onnx
from onnx import TensorProto

sys.path.insert(0, str(Path(__file__).resolve().parent))
from onnx_fp16 import infer_value_types  # noqa: E402

TYPE = {v: k for k, v in TensorProto.DataType.items()}
target = "/model/model/backbone/conv_encoder/model/swin/encoder/layers.0/blocks.1/Equal_1"

path = Path(sys.argv[1])
m = onnx.load(str(path))
g = m.graph
t = infer_value_types(g)

producer = {o: n for n in g.node for o in n.output}

node = next((n for n in g.node if n.name == target), None)
if node is None:
    raise SystemExit("노드 없음")

print(f"노드 {node.name}")


def dump(name: str, depth: int = 0, seen=None):
    seen = seen or set()
    pad = "  " * depth
    ty = TYPE.get(t.get(name), "UNKNOWN")
    n = producer.get(name)
    src = f"{n.op_type}" if n else "init/graph-input"
    print(f"{pad}{name.split('/')[-1]:45s} {ty:10s} <- {src}")
    if depth >= 4 or n is None or name in seen:
        return
    seen.add(name)
    for i in n.input:
        dump(i, depth + 1, seen)


for inp in node.input:
    dump(inp)
    print()
