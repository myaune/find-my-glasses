"""YOLO-World — 폴백 후보.

모델 자체는 GPL-3.0, 실행에 필요한 ultralytics 패키지는 AGPL-3.0이다.
데스크탑 벤치마크는 배포가 아니므로 라이선스 의무가 발생하지 않지만,
앱 탑재 시점에는 기획서 5·13절의 판단이 그대로 적용된다.

기본 비활성. 쓰려면:  uv add ultralytics
"""
from __future__ import annotations

from PIL import Image

from .base import Det, match_positive


class YoloWorldDetector:
    supports_embed_ensemble = False

    def __init__(self, name: str, hf_id: str, imgsz: int = 640):
        try:
            from ultralytics import YOLOWorld
        except ImportError as e:
            raise ImportError(
                "YOLO-World 를 쓰려면 ultralytics 가 필요합니다 (AGPL-3.0).\n"
                "  uv add ultralytics"
            ) from e
        self.name = name
        self.hf_id = hf_id
        self.imgsz = imgsz
        self.model = YOLOWorld(hf_id)
        self.model.to("cpu")  # 폰과 비교하려면 CPU 로 잰다
        self._classes: list[str] | None = None

    def param_bytes(self) -> int:
        return sum(p.numel() * p.element_size() for p in self.model.model.parameters())

    def detect(self, image: Image.Image, positives: list[str],
               negatives: list[str], threshold: float) -> list[Det]:
        classes = list(positives) + list(negatives)
        if classes != self._classes:
            self.model.set_classes(classes)
            self._classes = classes

        res = self.model.predict(image, imgsz=self.imgsz, conf=threshold,
                                 device="cpu", verbose=False)[0]
        dets: list[Det] = []
        for b in res.boxes:
            lab = classes[int(b.cls.item())]
            x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
            dets.append(Det(lab, float(b.conf.item()), (x1, y1, x2, y2),
                            match_positive(lab, positives, negatives)))
        return dets
