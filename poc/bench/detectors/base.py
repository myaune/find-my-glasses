from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from PIL import Image


@dataclass
class Det:
    label: str                       # 모델이 붙인 텍스트 라벨
    score: float
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 (픽셀)
    is_positive: bool                # 라벨이 안경 계열인가


class Detector(Protocol):
    name: str
    hf_id: str

    def detect(
        self,
        image: Image.Image,
        positives: list[str],
        negatives: list[str],
        threshold: float,
    ) -> list[Det]: ...

    def param_bytes(self) -> int: ...


def match_positive(label: str, positives: list[str],
                   negatives: Sequence[str] = ()) -> bool:
    """모델이 돌려준 라벨이 안경 계열인지 판정.

    Grounding DINO 는 text_threshold 를 넘은 토큰을 전부 이어붙인 구를
    돌려준다. 임계값이 낮으면 "glasses keys phone scissors pen remote
    control cup" 같은 뭉텅이가 나오는데, 여기에 "glasses" 가 들어있다고
    안경으로 세면 안 된다. 네거티브 어휘가 섞인 라벨은 양성에서 제외한다.
    """
    lab = label.strip().lower()
    if not lab:
        return False
    if any(n.strip().lower() in lab for n in negatives):
        return False
    if "sunglasses" in lab:
        return False
    for p in positives:
        pl = p.lower()
        if pl in lab or lab in pl:
            return True
    return "glasses" in lab
