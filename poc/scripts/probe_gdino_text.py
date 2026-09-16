"""GroundingDinoModel.forward 에서 텍스트 브랜치가 어디서 들어가는지 확인한다.

기획서 6절은 어휘가 고정 1개이므로 텍스트 인코더를 빌드 타임에 제거하고
텍스트 임베딩을 구워넣는 것을 전제한다. 실제로 어느 지점을 잘라내면 되는지
소스에서 찾는다. 가중치를 로드하지 않으므로 GPU 를 쓰지 않는다.
"""
import inspect
import re

from transformers.models.grounding_dino import modeling_grounding_dino as M

src = inspect.getsource(M.GroundingDinoModel.forward)
lines = src.splitlines()

print(f"총 {len(lines)}줄\n")
keys = ("text_backbone", "text_projection", "text_token_mask", "text_self_attention",
        "attention_mask", "encoder(", "text_features", "text_outputs", "position_ids")
for i, line in enumerate(lines):
    if any(k in line for k in keys):
        print(f"{i:4d}  {line}")

print("\n--- encoder 호출부 앞뒤 ---")
for i, line in enumerate(lines):
    if re.search(r"self\.encoder\(", line):
        for j in range(max(0, i - 22), min(len(lines), i + 22)):
            print(f"{j:4d}  {lines[j]}")
        break
