"""Phase 0 벤치마크 설정.

기획서 5절(프롬프트)·11절(실험 그리드)에 대응한다.
"""
from __future__ import annotations

# ── 프롬프트 ────────────────────────────────────────────────────────────────
# O365 클래스명과 정확히 일치하는 "glasses"가 1순위 검증 대상.
POSITIVE_PROMPTS: list[str] = [
    "glasses",
    "eyeglasses",
    "spectacles",
    "a pair of eyeglasses",
]

# 네거티브 어휘를 같이 넣어 경쟁시킨다. 단일 클래스 open-vocab은 오탐이 심하다.
NEGATIVE_PROMPTS: list[str] = [
    "keys",
    "phone",
    "scissors",
    "pen",
    "remote control",
    "cup",
]

# 프롬프트 모드
#   개별 4종            → POSITIVE_PROMPTS 각각을 단독 투입
#   ensemble_embed     → 4종의 텍스트 임베딩을 평균해 질의 1개로 (OWLv2만 가능)
#   ensemble_score     → analyze 단계에서 개별 4종 결과의 max를 취함 (추가 추론 없음)
PROMPT_MODE_EMBED = "ensemble_embed"
PROMPT_MODE_SCORE = "ensemble_score"

# ── 추론 ────────────────────────────────────────────────────────────────────
# 임계값 스윕을 오프라인에서 하기 위해, 추론은 아주 낮은 값으로 한 번만 돌리고
# 원시 검출을 전부 CSV에 남긴다. 스윕 때마다 재추론하지 않는다.
RAW_THRESHOLD: float = 0.03
MAX_DETS_PER_FRAME: int = 100

# 임계값 스윕 구간
SWEEP_THRESHOLDS: list[float] = [round(0.05 * i, 2) for i in range(1, 13)]  # 0.05 ~ 0.60

# ── 영상 ────────────────────────────────────────────────────────────────────
# 기획서 6절: 2~3 FPS 추론을 전제로 한다.
VIDEO_SAMPLE_FPS: float = 2.5

# ── 세션 판정 (기획서 9절 temporal detection) ───────────────────────────────
# 연속 프레임에서 비슷한 위치에 반복 검출되면 "찾았다"로 친다.
SESSION_WINDOW_S: float = 15.0   # Go/No-Go 기준 창
SESSION_HITS_REQUIRED: int = 3   # 트랙 확정에 필요한 검출 횟수
SESSION_TRACK_GAP_S: float = 1.0  # 이보다 오래 끊기면 트랙 단절
SESSION_TRACK_IOU: float = 0.1    # 같은 트랙으로 묶을 최소 IoU

# ── 모델 ────────────────────────────────────────────────────────────────────
MODELS: dict[str, dict] = {
    "grounding-dino-tiny": {
        "kind": "gdino",
        "hf_id": "IDEA-Research/grounding-dino-tiny",
        "license": "Apache-2.0",
        "supports_embed_ensemble": False,  # 텍스트가 인코더에서 융합됨 — 사후 평균 불가
    },
    "owlv2-base": {
        "kind": "owlv2",
        "hf_id": "google/owlv2-base-patch16-ensemble",
        "license": "Apache-2.0",
        "supports_embed_ensemble": True,
    },
    # 폴백 후보. ultralytics(AGPL-3.0)가 필요해 기본 비활성.
    "yolo-world": {
        "kind": "yolo_world",
        "hf_id": "yolov8s-worldv2.pt",
        "license": "GPL-3.0 (runner: ultralytics AGPL-3.0)",
        "supports_embed_ensemble": False,
        "enabled_by_default": False,
    },
}

DEFAULT_MODELS: list[str] = ["grounding-dino-tiny", "owlv2-base"]

# Grounding DINO 는 박스 임계값과 별개로 "어떤 텍스트 토큰을 라벨에 넣을지"를
# 정하는 임계값을 따로 받는다. 이 값이 낮으면 약하게 걸린 토큰까지 전부 이어붙어
# "glasses keys phone scissors pen remote control cup" 같은 라벨이 나오고,
# 안경 검출인지 아닌지 판별이 불가능해진다.
TEXT_THRESHOLD: float = 0.25

# 렌더링에 그릴 최소 점수. RAW_THRESHOLD 로 그리면 박스가 수백 개라 눈으로 못 본다.
DRAW_THRESHOLD: float = 0.25

# ── 0b 배포 포맷 ────────────────────────────────────────────────────────────
# export_onnx.py 가 만든 모델은 프롬프트가 상수로 구워져 있어 런타임에 못 바꾼다.
# 비교는 세 갈래로 본다.
#   FP32 torch vs FP32 ONNX  → 입력 800x800 고정(전처리) 차이
#   FP32 ONNX  vs FP16 ONNX  → 양자화 차이
ONNX_MODELS: dict[str, dict] = {
    "gdino-onnx-fp32": {
        "kind": "gdino_onnx",
        "onnx_path": "../runs/0b/gdino-tiny-eyeglasses-fp32.onnx",
        "baked_prompt": "eyeglasses",
        "license": "Apache-2.0",
        "hf_id": "IDEA-Research/grounding-dino-tiny",
        "supports_embed_ensemble": False,
    },
    "gdino-onnx-fp16": {
        "kind": "gdino_onnx",
        "onnx_path": "../runs/0b/gdino-tiny-eyeglasses-fp16.onnx",
        "baked_prompt": "eyeglasses",
        "license": "Apache-2.0",
        "hf_id": "IDEA-Research/grounding-dino-tiny",
        "supports_embed_ensemble": False,
    },
}
MODELS.update(ONNX_MODELS)

# ── 모바일 후보 (Phase 1 실측 후 추가) ──────────────────────────────────────
# GDINO Tiny 는 SD685 에서 35초였다. 데스크탑 CPU 3.1초에서 이미 예측 가능했고
# 이 관문(scripts/latency_gate.py)을 먼저 돌렸어야 했다.
#
#   데스크탑 CPU 중앙값 / SD685 추정(8~15배)
#     GDINO Tiny   800   3100ms  →  25~46초      실측 35초
#     YOLO-World s 640     89ms  →  0.7~1.3초
#     YOLO-World s 512     62ms  →  0.5~0.9초
#     YOLO-World s 416     36ms  →  0.3~0.5초    관문 통과
#     YOLO-World s 320     32ms  →  0.3~0.5초    관문 통과
#
# 해상도를 낮추면 작은 물체가 먼저 죽는다. 안경이 그 작은 물체이므로
# 속도만 보고 고를 수 없다. 해상도별 검출률을 같이 재야 한다.
for _sz in (640, 512, 416, 320):
    MODELS[f"yolo-world-{_sz}"] = {
        "kind": "yolo_world",
        "hf_id": "yolov8s-worldv2.pt",
        "imgsz": _sz,
        "license": "GPL-3.0 (러너 ultralytics AGPL-3.0)",
        "supports_embed_ensemble": False,
    }
