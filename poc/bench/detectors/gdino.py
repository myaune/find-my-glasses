"""Grounding DINO (Apache-2.0).

텍스트가 인코더 전 단계에 걸쳐 cross-attention으로 융합되는 구조라,
텍스트 임베딩을 사후에 평균내는 방식의 앙상블은 적용할 수 없다.
앙상블은 analyze 단계의 스코어 레벨로 대신한다.
"""
from __future__ import annotations

import torch
from PIL import Image
from transformers import AutoProcessor, GroundingDinoForObjectDetection

from .base import Det, match_positive


class GroundingDinoDetector:
    supports_embed_ensemble = False

    def __init__(self, name: str, hf_id: str, device: str | None = None,
                 text_threshold: float = 0.25):
        self.name = name
        self.hf_id = hf_id
        # 박스 임계값과 별개로 둔다. 이 값이 낮으면 약하게 걸린 토큰까지 라벨에
        # 이어붙어 "glasses keys phone ..." 같은 뭉텅이가 나오고, 안경 검출인지
        # 아닌지 구분이 불가능해진다.
        self.text_threshold = text_threshold
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = AutoProcessor.from_pretrained(hf_id)
        self.model = GroundingDinoForObjectDetection.from_pretrained(hf_id).to(self.device).eval()

    def param_bytes(self) -> int:
        return sum(p.numel() * p.element_size() for p in self.model.parameters())

    @staticmethod
    def _build_prompt(terms: list[str]) -> str:
        # Grounding DINO는 소문자 + 마침표 구분 형식을 기대한다.
        return ". ".join(t.strip().lower() for t in terms) + "."

    @torch.inference_mode()
    def detect(self, image: Image.Image, positives: list[str],
               negatives: list[str], threshold: float) -> list[Det]:
        terms = list(positives) + list(negatives)
        text = self._build_prompt(terms)

        inputs = self.processor(images=image, text=text, return_tensors="pt").to(self.device)
        outputs = self.model(**inputs)

        results = self.processor.post_process_grounded_object_detection(
            outputs,
            input_ids=inputs["input_ids"],
            threshold=threshold,
            text_threshold=self.text_threshold,
            target_sizes=[(image.height, image.width)],
        )[0]

        labels = results.get("text_labels", results.get("labels", []))
        dets: list[Det] = []
        for box, score, label in zip(results["boxes"], results["scores"], labels):
            lab = label if isinstance(label, str) else str(label)
            x1, y1, x2, y2 = (float(v) for v in box.tolist())
            dets.append(Det(lab, float(score), (x1, y1, x2, y2),
                            match_positive(lab, positives, negatives)))
        return dets
