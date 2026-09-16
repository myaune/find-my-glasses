"""Phase 0a — 추론을 한 번만 돌려 원시 검출을 CSV로 남긴다.

임계값 스윕과 세션 판정은 analyze.py 가 이 CSV만 보고 계산한다.
추론은 RAW_THRESHOLD 로 딱 한 번 돈다.

사용 예:
    uv run python -m bench.run_detect --data ../data --out ../runs/0a
    uv run python -m bench.run_detect --models owlv2-base --no-annotate
"""
from __future__ import annotations

import argparse
import csv
import platform
import time
from pathlib import Path

import torch
from tqdm import tqdm

from . import config as C
from .detectors import build
from .draw import annotate, save
from .sources import discover, iter_frames

RAW_FIELDS = [
    "source_id", "source_type", "frame_idx", "timestamp_s",
    "img_w", "img_h",
    "model", "prompt_mode", "precision",
    "label", "is_positive", "score",
    "x1", "y1", "x2", "y2",
    "latency_ms",
]


def prompt_modes(detector) -> list[tuple[str, list[str]]]:
    """(모드 이름, positives) 목록."""
    # ONNX 모델은 프롬프트가 그래프에 구워져 있어 하나만 돈다.
    fixed = getattr(detector, "fixed_prompt", None)
    if fixed:
        return [(fixed, [fixed])]
    modes: list[tuple[str, list[str]]] = [(p, [p]) for p in C.POSITIVE_PROMPTS]
    if getattr(detector, "supports_embed_ensemble", False):
        modes.append((C.PROMPT_MODE_EMBED, list(C.POSITIVE_PROMPTS)))
    return modes


def run_one(detector, mode: str, positives: list[str], image, threshold: float):
    t0 = time.perf_counter()
    if mode == C.PROMPT_MODE_EMBED:
        dets = detector.detect_embed_ensemble(image, positives, C.NEGATIVE_PROMPTS, threshold)
    else:
        dets = detector.detect(image, positives, C.NEGATIVE_PROMPTS, threshold)
    return dets, (time.perf_counter() - t0) * 1000.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("../data"))
    ap.add_argument("--out", type=Path, default=Path("../runs/0a"))
    ap.add_argument("--models", nargs="*", default=C.DEFAULT_MODELS)
    ap.add_argument("--threshold", type=float, default=C.RAW_THRESHOLD,
                    help="원시 기록 임계값. 낮게 두고 스윕은 오프라인으로 한다.")
    ap.add_argument("--text-threshold", type=float, default=C.TEXT_THRESHOLD,
                    help="Grounding DINO 라벨 구성 임계값. 박스 임계값과 별개다.")
    ap.add_argument("--draw-threshold", type=float, default=C.DRAW_THRESHOLD,
                    help="렌더링에 그릴 최소 점수. 낮으면 박스가 수백 개라 눈으로 못 본다.")
    ap.add_argument("--sample-fps", type=float, default=C.VIDEO_SAMPLE_FPS)
    ap.add_argument("--precision", choices=["fp32", "fp16"], default="fp32",
                    help="0a 는 fp32 상한선 측정")
    ap.add_argument("--no-annotate", action="store_true")
    ap.add_argument("--annotate-mode", default="glasses",
                    help="어느 프롬프트 모드의 결과를 그릴지")
    args = ap.parse_args()

    files = discover(args.data)
    if not files:
        raise SystemExit(
            f"입력이 없습니다: {args.data.resolve()}\n"
            f"  이미지는 {args.data}/images/, 영상은 {args.data}/videos/ 에 넣어주세요."
        )

    args.out.mkdir(parents=True, exist_ok=True)
    raw_path = args.out / "raw_detections.csv"
    meta_path = args.out / "models.csv"

    print(f"입력 {len(files)}개")
    for f in files:
        print(f"  {f.relative_to(args.data) if args.data in f.parents else f.name}")

    raw_f = raw_path.open("w", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(raw_f, fieldnames=RAW_FIELDS)
    writer.writeheader()

    meta_rows = []

    try:
        for model_key in args.models:
            spec = C.MODELS[model_key]
            print(f"\n=== {model_key}  ({spec['hf_id']}) ===")
            t_load = time.perf_counter()
            det = build(model_key)
            if hasattr(det, "text_threshold"):
                det.text_threshold = args.text_threshold
            load_s = time.perf_counter() - t_load

            # ONNX 모델은 파일 자체가 이미 해당 정밀도라 여기서 바꾸지 않는다.
            if args.precision == "fp16" and hasattr(det, "model"):
                det.model.half()

            pbytes = det.param_bytes()
            print(f"  로드 {load_s:.1f}s / 파라미터 {pbytes / 1024**2:.1f} MB ({args.precision})")
            meta_rows.append({
                "model": model_key,
                "hf_id": spec["hf_id"],
                "license": spec["license"],
                "precision": args.precision,
                "param_mb": round(pbytes / 1024**2, 2),
                "load_s": round(load_s, 2),
                "supports_embed_ensemble": spec["supports_embed_ensemble"],
            })

            modes = prompt_modes(det)
            for path in files:
                frames = list(iter_frames(path, args.sample_fps))
                bar = tqdm(frames, desc=f"  {path.name}", unit="frame", leave=False)
                for fr in bar:
                    for mode, positives in modes:
                        dets, ms = run_one(det, mode, positives, fr.image, args.threshold)
                        dets = sorted(dets, key=lambda d: -d.score)[:C.MAX_DETS_PER_FRAME]

                        for d in dets:
                            writer.writerow({
                                "source_id": fr.source_id,
                                "source_type": fr.source_type,
                                "frame_idx": fr.frame_idx,
                                "timestamp_s": round(fr.timestamp_s, 3),
                                "img_w": fr.image.width,
                                "img_h": fr.image.height,
                                "model": model_key,
                                "prompt_mode": mode,
                                "precision": args.precision,
                                "label": d.label,
                                "is_positive": int(d.is_positive),
                                "score": round(d.score, 5),
                                "x1": round(d.box[0], 1), "y1": round(d.box[1], 1),
                                "x2": round(d.box[2], 1), "y2": round(d.box[3], 1),
                                "latency_ms": round(ms, 1),
                            })
                        if not dets:
                            # 검출 0개인 프레임도 레이턴시·커버리지를 위해 남긴다
                            writer.writerow({
                                "source_id": fr.source_id, "source_type": fr.source_type,
                                "frame_idx": fr.frame_idx, "timestamp_s": round(fr.timestamp_s, 3),
                                "img_w": fr.image.width, "img_h": fr.image.height,
                                "model": model_key, "prompt_mode": mode,
                                "precision": args.precision,
                                "label": "", "is_positive": 0, "score": "",
                                "x1": "", "y1": "", "x2": "", "y2": "",
                                "latency_ms": round(ms, 1),
                            })

                        if (not args.no_annotate) and mode == args.annotate_mode:
                            shown = [d for d in dets if d.score >= args.draw_threshold]
                            img = annotate(fr.image, shown,
                                           f"{model_key} | {mode} | {fr.source_id}#{fr.frame_idx}"
                                           f" | ≥{args.draw_threshold}")
                            sub = "images" if fr.source_type == "image" else "videos"
                            save(img, args.out / "annotated" / sub / model_key /
                                 f"{fr.source_id}_{fr.frame_idx:04d}.jpg")
                raw_f.flush()

            del det
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    finally:
        raw_f.close()

    with meta_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(meta_rows[0].keys()))
        w.writeheader()
        w.writerows(meta_rows)

    print(f"\n원시 검출 → {raw_path}")
    print(f"모델 정보 → {meta_path}")
    if not args.no_annotate:
        print(f"렌더링   → {args.out / 'annotated'}")
    print(f"\n환경: {platform.platform()} / "
          f"{torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
    print("다음: uv run python -m bench.analyze --run", args.out)


if __name__ == "__main__":
    main()
