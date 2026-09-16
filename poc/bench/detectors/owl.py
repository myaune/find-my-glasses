"""OWLv2 (Apache-2.0).

image_text_embedder / class_predictor 가 노출돼 있어, 여러 프롬프트의 텍스트
임베딩을 평균낸 질의 하나로 교체하는 진짜 임베딩 앙상블이 가능하다.
"""
from __future__ import annotations

import torch
from PIL import Image
from transformers import AutoProcessor, Owlv2ForObjectDetection
from transformers.models.owlv2.modeling_owlv2 import Owlv2ObjectDetectionOutput

from .base import Det, match_positive


class Owlv2Detector:
    supports_embed_ensemble = True

    def __init__(self, name: str, hf_id: str, device: str | None = None):
        self.name = name
        self.hf_id = hf_id
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = AutoProcessor.from_pretrained(hf_id)
        self.model = Owlv2ForObjectDetection.from_pretrained(hf_id).to(self.device).eval()

    def param_bytes(self) -> int:
        return sum(p.numel() * p.element_size() for p in self.model.parameters())

    @staticmethod
    def _target_size(image: Image.Image) -> tuple[int, int]:
        """OWLv2 전처리는 긴 변 기준으로 정사각 패딩을 한다.

        모델이 내놓는 정규화 좌표는 패딩된 정사각형 기준이므로, 원본 좌표로
        되돌리려면 target_size 에 max(H, W) 정사각을 넣어야 한다.
        """
        s = max(image.height, image.width)
        return (s, s)

    def _to_dets(self, result, image: Image.Image, queries: list[str],
                 positives: list[str], negatives: list[str]) -> list[Det]:
        labels = result.get("text_labels")
        if labels is None:
            labels = [queries[int(i)] for i in result.get("labels", [])]
        dets: list[Det] = []
        for box, score, label in zip(result["boxes"], result["scores"], labels):
            lab = label if isinstance(label, str) else str(label)
            x1, y1, x2, y2 = (float(v) for v in box.tolist())
            # 패딩 영역으로 삐져나온 좌표를 원본 크기로 자른다.
            x1 = max(0.0, min(x1, image.width))
            x2 = max(0.0, min(x2, image.width))
            y1 = max(0.0, min(y1, image.height))
            y2 = max(0.0, min(y2, image.height))
            if x2 <= x1 or y2 <= y1:
                continue
            dets.append(Det(lab, float(score), (x1, y1, x2, y2),
                            match_positive(lab, positives, negatives)))
        return dets

    @torch.inference_mode()
    def detect(self, image: Image.Image, positives: list[str],
               negatives: list[str], threshold: float) -> list[Det]:
        queries = list(positives) + list(negatives)
        inputs = self.processor(text=[queries], images=image, return_tensors="pt").to(self.device)
        outputs = self.model(**inputs)
        result = self.processor.post_process_grounded_object_detection(
            outputs=outputs,
            threshold=threshold,
            target_sizes=[self._target_size(image)],
            text_labels=[queries],
        )[0]
        return self._to_dets(result, image, queries, positives, negatives)

    @torch.inference_mode()
    def detect_embed_ensemble(self, image: Image.Image, positives: list[str],
                              negatives: list[str], threshold: float) -> list[Det]:
        """positives 의 텍스트 임베딩을 평균내 질의 1개로 합친 뒤 검출."""
        queries = list(positives) + list(negatives)
        n_pos = len(positives)
        inputs = self.processor(text=[queries], images=image, return_tensors="pt").to(self.device)

        query_embeds, feature_map, _ = self.model.image_text_embedder(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            attention_mask=inputs["attention_mask"],
        )

        b, ph, pw, hid = feature_map.shape
        image_feats = feature_map.reshape(b, ph * pw, hid)

        max_q = inputs["input_ids"].shape[0] // b
        query_embeds = query_embeds.reshape(b, max_q, query_embeds.shape[-1])

        # positives 평균 → 단위벡터로 정규화 (class_predictor 가 다시 정규화해도 무해)
        pos_mean = query_embeds[:, :n_pos, :].mean(dim=1, keepdim=True)
        pos_mean = pos_mean / (pos_mean.norm(dim=-1, keepdim=True) + 1e-6)
        fused = torch.cat([pos_mean, query_embeds[:, n_pos:, :]], dim=1)

        ids = inputs["input_ids"].reshape(b, max_q, -1)
        mask = ids[..., 0] > 0
        fused_mask = torch.cat([mask[:, :1], mask[:, n_pos:]], dim=1)

        pred_logits, class_embeds = self.model.class_predictor(image_feats, fused, fused_mask)
        pred_boxes = self.model.box_predictor(image_feats, feature_map)

        outputs = Owlv2ObjectDetectionOutput(
            image_embeds=feature_map,
            text_embeds=fused,
            pred_boxes=pred_boxes,
            logits=pred_logits,
            class_embeds=class_embeds,
        )

        fused_queries = ["+".join(positives)] + list(negatives)
        result = self.processor.post_process_grounded_object_detection(
            outputs=outputs,
            threshold=threshold,
            target_sizes=[self._target_size(image)],
            text_labels=[fused_queries],
        )[0]
        # 합쳐진 질의는 라벨이 "glasses+eyeglasses+..." 형태라 positives 로 인식된다.
        return self._to_dets(result, image, fused_queries, positives, negatives)
