"""Phase 0b — ONNX Runtime 으로 도는 Grounding DINO.

export_onnx.py 가 만든 모델은 텍스트가 상수로 구워져 있다. 따라서 프롬프트를
런타임에 바꿀 수 없고, 익스포트할 때 쓴 조합만 검출한다.

후처리는 직접 구현하지 않고 transformers 의
GroundingDinoProcessor.post_process_grounded_object_detection 을 그대로
호출한다. 재구현하면 FP32 경로와 미묘하게 달라져 비교가 오염된다.

입력 크기는 익스포트 시점에 800x800 으로 고정돼 있다. PyTorch 경로는
짧은 변 800 기준 가변 크기를 쓰므로 전처리가 다르다. 이 차이를 분리하려면
fp32 ONNX 와 fp16 ONNX 를 같이 돌려 비교한다.

    FP32 torch  vs  FP32 ONNX   → 전처리(고정 크기) 차이
    FP32 ONNX   vs  FP16 ONNX   → 양자화 차이
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from PIL import Image
from transformers import AutoProcessor
from transformers.models.grounding_dino.modeling_grounding_dino import (
    GroundingDinoObjectDetectionOutput,
)

from ..config import NEGATIVE_PROMPTS
from .base import Det, match_positive


class GroundingDinoOnnxDetector:
    supports_embed_ensemble = False

    def __init__(self, name: str, onnx_path: str | Path,
                 hf_id: str = "IDEA-Research/grounding-dino-tiny",
                 baked_prompt: str = "eyeglasses",
                 size: int = 800,
                 text_threshold: float = 0.25,
                 providers: list[str] | None = None):
        self.name = name
        self.hf_id = hf_id
        self.onnx_path = Path(onnx_path)
        self.baked_prompt = baked_prompt
        # 프롬프트가 그래프에 상수로 구워져 있어 런타임에 바꿀 수 없다.
        self.fixed_prompt = baked_prompt
        self.size = size
        self.text_threshold = text_threshold

        self.processor = AutoProcessor.from_pretrained(hf_id)
        text = ". ".join([baked_prompt] + [n.lower() for n in NEGATIVE_PROMPTS]) + "."
        enc = self.processor.tokenizer(text, return_tensors="pt")
        self.input_ids = enc["input_ids"]

        so = ort.SessionOptions()
        so.log_severity_level = 3
        self.sess = ort.InferenceSession(
            str(self.onnx_path), so,
            providers=providers or ["CPUExecutionProvider"])
        inp = self.sess.get_inputs()[0]
        self.input_name = inp.name
        self.input_is_fp16 = "float16" in inp.type

        ip = self.processor.image_processor
        self.mean = np.array(ip.image_mean, dtype=np.float32).reshape(3, 1, 1)
        self.std = np.array(ip.image_std, dtype=np.float32).reshape(3, 1, 1)

    def param_bytes(self) -> int:
        """ONNX 파일 크기. 실제 앱에 들어가는 값이다."""
        return self.onnx_path.stat().st_size

    def _letterbox(self, image: Image.Image) -> tuple[np.ndarray, float, int, int]:
        """가로세로비를 유지한 채 size x size 로 맞추고 남는 곳은 0 으로 채운다."""
        w, h = image.width, image.height
        s = self.size / max(w, h)
        nw, nh = max(1, round(w * s)), max(1, round(h * s))
        resized = image.resize((nw, nh), Image.BILINEAR)
        canvas = Image.new("RGB", (self.size, self.size), (0, 0, 0))
        pad_x, pad_y = (self.size - nw) // 2, (self.size - nh) // 2
        canvas.paste(resized, (pad_x, pad_y))

        arr = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1) / 255.0
        arr = (arr - self.mean) / self.std
        return arr[None], s, pad_x, pad_y

    def detect(self, image: Image.Image, positives: list[str],
               negatives: list[str], threshold: float) -> list[Det]:
        x, scale, pad_x, pad_y = self._letterbox(image)
        x = x.astype(np.float16 if self.input_is_fp16 else np.float32)
        logits, boxes = self.sess.run(None, {self.input_name: x})

        outputs = GroundingDinoObjectDetectionOutput(
            logits=torch.from_numpy(logits.astype(np.float32)),
            pred_boxes=torch.from_numpy(boxes.astype(np.float32)),
        )
        results = self.processor.post_process_grounded_object_detection(
            outputs,
            input_ids=self.input_ids,
            threshold=threshold,
            text_threshold=self.text_threshold,
            target_sizes=[(self.size, self.size)],
        )[0]

        labels = results.get("text_labels", results.get("labels", []))
        dets: list[Det] = []
        for box, score, label in zip(results["boxes"], results["scores"], labels):
            lab = label if isinstance(label, str) else str(label)
            x1, y1, x2, y2 = (float(v) for v in box.tolist())
            # letterbox 좌표 → 원본 좌표
            x1 = (x1 - pad_x) / scale
            x2 = (x2 - pad_x) / scale
            y1 = (y1 - pad_y) / scale
            y2 = (y2 - pad_y) / scale
            x1, x2 = max(0.0, x1), min(float(image.width), x2)
            y1, y2 = max(0.0, y1), min(float(image.height), y2)
            if x2 <= x1 or y2 <= y1:
                continue
            dets.append(Det(lab, float(score), (x1, y1, x2, y2),
                            match_positive(lab, positives, negatives)))
        return dets
