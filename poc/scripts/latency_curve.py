"""추론이 느려지면 발화까지 몇 초 걸리는가.

기획서 11절 Go/No-Go 의 "프레임 레이턴시 ≤ 500ms" 는 수단이지 목적이 아니다.
목적은 "15초 안에 찾는가" 다. 실기기 추론 속도가 정해지면 이 표로 바로
"그 속도면 몇 초에 찾는지" 를 대입할 수 있다.

추론을 다시 돌리지 않는다. 2.5 FPS 로 샘플링해 둔 영상 검출을 stride 로
솎아내면 더 느린 추론 속도를 흉내낼 수 있다.

    stride 1 → 2.50 FPS (0.40s/추론)
    stride 2 → 1.25 FPS (0.80s/추론)
    stride 3 → 0.83 FPS (1.20s/추론)
    ...

    uv run python scripts/latency_curve.py --run ../runs/0a
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench import config as C  # noqa: E402
from bench.analyze import build_tracks  # noqa: E402

STRIDES = [1, 2, 3, 4, 5, 6, 8]


def time_to_fire(dets: list[dict], hits_required: int, gap_s: float) -> float | None:
    best = None
    for tr in build_tracks(dets, gap_s=gap_s):
        if len(tr) >= hits_required:
            t = float(tr[hits_required - 1]["timestamp_s"])
            best = t if best is None else min(best, t)
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=Path("../runs/0a"))
    ap.add_argument("--model", default="grounding-dino-tiny")
    ap.add_argument("--prompt", default="eyeglasses")
    ap.add_argument("--threshold", type=float, default=0.40)
    ap.add_argument("--base-fps", type=float, default=C.VIDEO_SAMPLE_FPS)
    args = ap.parse_args()

    df = pd.read_csv(args.run / "raw_detections.csv")
    df = df[(df["model"] == args.model) & (df["prompt_mode"] == args.prompt)
            & (df["source_type"] == "video")]
    if df.empty:
        raise SystemExit("영상 검출이 없습니다.")

    for src, g in df.groupby("source_id"):
        dur = float(g["timestamp_s"].max())
        n_frames = int(g["frame_idx"].nunique())
        print(f"\n=== {src} — {dur:.1f}초, 샘플 {n_frames}프레임 "
              f"@{args.base_fps} FPS, 임계값 {args.threshold} ===")
        print("발화 시각은 '상한~하한' 이다. 상한은 자이로 앵커링이 완벽할 때,")
        print("하한은 화면 좌표 IoU 로만 묶을 때. 실제는 그 사이에 있다.\n")
        print(f"{'추론속도':>10} {'유효FPS':>8}  "
              f"{'발화(3회)':>13} {'발화(2회)':>13}  {'남은프레임':>9}")

        pos = g[g["score"].notna() & (g["is_positive"] == 1)
                & (g["score"] >= args.threshold)]

        for stride in STRIDES:
            keep = sorted(g["frame_idx"].unique())[::stride]
            sub = pos[pos["frame_idx"].isin(keep)].to_dict("records")
            eff_fps = args.base_fps / stride
            sec_per_inf = 1.0 / eff_fps

            gap = max(C.SESSION_TRACK_GAP_S, 2.5 * sec_per_inf)
            ordered = sorted(sub, key=lambda x: x["timestamp_s"])

            cells = []
            for hits in (3, 2):
                # 하한 — 화면 좌표 IoU 로만 묶는다. 카메라가 움직이면 끊긴다.
                lo = time_to_fire(sub, hits, gap_s=gap)
                # 상한 — 위치를 무시하고 시간순 N 번째 검출. 자이로 앵커링이
                # 완벽하다고 가정한 경우에 해당한다.
                hi = (float(ordered[hits - 1]["timestamp_s"])
                      if len(ordered) >= hits else None)
                lo_s = f"{lo:.1f}" if lo is not None else "—"
                hi_s = f"{hi:.1f}" if hi is not None else "—"
                cells.append(f"{hi_s}~{lo_s}")

            print(f"{sec_per_inf:9.2f}s {eff_fps:8.2f}  "
                  f"{cells[0]:>13} {cells[1]:>13}  {len(keep):9d}")

    print("\n주의")
    print("  · 영상이 1개(8.2초)뿐이라 통계가 아니다. 경향만 본다.")
    print("  · stride 가 커지면 남은 프레임이 몇 개 안 돼 '실패' 가 표본 부족")
    print("    때문인지 실제 한계인지 구분되지 않는다.")
    print("  · 실제 앱은 자이로로 카메라 모션을 보상해 association 하므로")
    print("    (기획서 9절) 여기 수치는 보수적이다.")


if __name__ == "__main__":
    main()
