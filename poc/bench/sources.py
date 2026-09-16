"""입력 소스 — 이미지와 영상을 같은 Frame 스트림으로 정규화한다.

영상은 VIDEO_SAMPLE_FPS로 샘플링해 이미지와 동일한 파이프라인에 태운다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
from PIL import Image

from .config import VIDEO_SAMPLE_FPS

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".heic"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}


@dataclass
class Frame:
    source_id: str      # 파일명 (확장자 제외)
    source_type: str    # "image" | "video"
    frame_idx: int      # 소스 내 샘플 순번
    timestamp_s: float  # 영상 내 시각. 이미지는 0.0
    image: Image.Image


def _iter_image(path: Path) -> Iterator[Frame]:
    img = Image.open(path).convert("RGB")
    yield Frame(path.stem, "image", 0, 0.0, img)


def _iter_video(path: Path, sample_fps: float) -> Iterator[Frame]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"영상을 열 수 없습니다: {path}")
    try:
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        if src_fps <= 0:
            src_fps = 30.0  # 메타데이터가 없으면 가정
        step = max(1, round(src_fps / sample_fps))

        raw_idx = 0
        out_idx = 0
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            if raw_idx % step == 0:
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                yield Frame(
                    path.stem, "video", out_idx, raw_idx / src_fps,
                    Image.fromarray(rgb),
                )
                out_idx += 1
            raw_idx += 1
    finally:
        cap.release()


def discover(data_dir: Path) -> list[Path]:
    """data_dir 아래의 이미지·영상 파일을 모은다."""
    if not data_dir.exists():
        return []
    out = [
        p for p in sorted(data_dir.rglob("*"))
        if p.is_file() and p.suffix.lower() in (IMAGE_EXT | VIDEO_EXT)
    ]
    return out


def iter_frames(path: Path, sample_fps: float = VIDEO_SAMPLE_FPS) -> Iterator[Frame]:
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        yield from _iter_image(path)
    elif ext in VIDEO_EXT:
        yield from _iter_video(path, sample_fps)
    else:
        raise ValueError(f"지원하지 않는 형식: {path}")
