from __future__ import annotations

from ..config import MODELS
from .base import Det, Detector


def build(model_key: str) -> Detector:
    spec = MODELS[model_key]
    kind = spec["kind"]
    if kind == "gdino":
        from .gdino import GroundingDinoDetector
        return GroundingDinoDetector(model_key, spec["hf_id"])
    if kind == "owlv2":
        from .owl import Owlv2Detector
        return Owlv2Detector(model_key, spec["hf_id"])
    if kind == "yolo_world":
        from .yolo_world import YoloWorldDetector
        return YoloWorldDetector(model_key, spec["hf_id"],
                                 imgsz=spec.get("imgsz", 640))
    if kind == "gdino_onnx":
        from .gdino_onnx import GroundingDinoOnnxDetector
        return GroundingDinoOnnxDetector(
            model_key, spec["onnx_path"],
            hf_id=spec["hf_id"], baked_prompt=spec["baked_prompt"])
    raise ValueError(f"알 수 없는 모델 종류: {kind}")


__all__ = ["build", "Det", "Detector"]
