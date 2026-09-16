"""Phase 0 — 원시 검출 CSV를 읽어 임계값 스윕과 세션 판정을 계산한다.

추론은 하지 않는다. run_detect.py 가 남긴 raw_detections.csv 만 본다.

측정 단위는 프레임 recall 이 아니라 세션 성공률이다 (기획서 11절).

사용 예:
    uv run python -m bench.analyze --run ../runs/0a
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import config as C


# ── 유틸 ────────────────────────────────────────────────────────────────────
def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    ua = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / ua if ua > 0 else 0.0


def nms(rows: list[dict], thr: float = 0.5) -> list[dict]:
    kept: list[dict] = []
    for r in sorted(rows, key=lambda x: -x["score"]):
        box = (r["x1"], r["y1"], r["x2"], r["y2"])
        if all(iou(box, (k["x1"], k["y1"], k["x2"], k["y2"])) < thr for k in kept):
            kept.append(r)
    return kept


def add_score_ensemble(df: pd.DataFrame) -> pd.DataFrame:
    """개별 프롬프트 4종의 결과를 합쳐 ensemble_score 모드를 만든다.

    Grounding DINO 는 구조상 임베딩 앙상블이 불가능하므로 이쪽으로 대신한다.
    추가 추론 없이 기존 결과만 재조합한다.
    """
    singles = df[df["prompt_mode"].isin(C.POSITIVE_PROMPTS)]
    if singles.empty:
        return df

    out: list[dict] = []
    keys = ["model", "source_id", "source_type", "frame_idx"]
    for _, g in singles.groupby(keys, sort=False):
        pos_rows = g[g["has_det"] & (g["is_positive"] == 1)].to_dict("records")
        if pos_rows:
            for r in nms(pos_rows):
                r = dict(r)
                r["prompt_mode"] = C.PROMPT_MODE_SCORE
                out.append(r)
        else:
            b = dict(g.iloc[0].to_dict())
            b.update({
                "prompt_mode": C.PROMPT_MODE_SCORE,
                "label": "",
                "is_positive": 0,
                "score": float("nan"),
                "has_det": False,
            })
            out.append(b)

        # 네거티브도 최고점 하나는 남겨 오탐 경향을 본다
        neg_rows = g[g["has_det"] & (g["is_positive"] == 0)].to_dict("records")
        if neg_rows:
            n = dict(max(neg_rows, key=lambda x: x["score"]))
            n["prompt_mode"] = C.PROMPT_MODE_SCORE
            out.append(n)

    return pd.concat([df, pd.DataFrame(out)], ignore_index=True)


# ── 네거티브 컨트롤 ─────────────────────────────────────────────────────────
def load_no_glasses(data_dir: Path) -> set[str]:
    """안경이 없는 소스 목록. 오탐 측정용 네거티브 컨트롤.

    data/no_glasses.txt 에 파일명(확장자 무관)을 한 줄에 하나씩 적는다.
    """
    path = data_dir / "no_glasses.txt"
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(Path(line).stem)
    return out


# ── 이미지 (1단계) ──────────────────────────────────────────────────────────
def sweep_images(df: pd.DataFrame, no_glasses: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    imgs = df[df["source_type"] == "image"]
    if imgs.empty:
        return pd.DataFrame(), pd.DataFrame()

    def condition(src: str) -> str:
        # make_degraded.py 는 "<원본>__<조건>" 으로 이름을 붙인다.
        return src.split("__", 1)[1] if "__" in src else "orig"

    per_image: list[dict] = []
    for (model, mode, src), g in imgs.groupby(["model", "prompt_mode", "source_id"]):
        pos = g[g["has_det"] & (g["is_positive"] == 1)]
        neg = g[g["has_det"] & (g["is_positive"] == 0)]
        per_image.append({
            "model": model,
            "prompt_mode": mode,
            "source_id": src,
            "condition": condition(src),
            "has_glasses": int(src.split("__", 1)[0] not in no_glasses
                               and src not in no_glasses),
            "top_positive_score": float(pos["score"].max()) if not pos.empty else 0.0,
            "n_positive_dets": int(len(pos)),
            "top_negative_score": float(neg["score"].max()) if not neg.empty else 0.0,
            "top_negative_label": (neg.loc[neg["score"].idxmax(), "label"] if not neg.empty else ""),
        })
    per_image_df = pd.DataFrame(per_image)

    rows: list[dict] = []
    multi_cond = per_image_df["condition"].nunique() > 1
    group_keys = (["model", "prompt_mode", "condition"] if multi_cond
                  else ["model", "prompt_mode"])
    for key, g in per_image_df.groupby(group_keys):
        model, mode = key[0], key[1]
        cond = key[2] if multi_cond else "orig"
        yes = g[g["has_glasses"] == 1]   # 안경 있는 사진 → recall
        no = g[g["has_glasses"] == 0]    # 안경 없는 사진 → false positive
        for t in C.SWEEP_THRESHOLDS:
            hit = int((yes["top_positive_score"] >= t).sum())
            fp = int((no["top_positive_score"] >= t).sum())
            rows.append({
                "model": model,
                "prompt_mode": mode,
                "condition": cond,
                "threshold": t,
                "n_with_glasses": int(len(yes)),
                "n_detected": hit,
                "recall": round(hit / len(yes), 3) if len(yes) else None,
                "n_without_glasses": int(len(no)),
                "n_false_positive": fp,
                "fp_rate": round(fp / len(no), 3) if len(no) else None,
            })
    return pd.DataFrame(rows), per_image_df


# ── 영상 (2단계) ────────────────────────────────────────────────────────────
def build_tracks(dets: list[dict], gap_s: float | None = None) -> list[list[dict]]:
    """시간순 검출을 IoU + 시간 간격으로 묶어 트랙을 만든다.

    주의: 실제 앱은 자이로로 카메라 모션을 보상한 좌표계에서 association 한다
    (기획서 9절). 오프라인 영상에는 자이로가 없어 화면 좌표 IoU 로만 묶으므로
    여기 수치는 실제보다 보수적으로 나올 수 있다.
    """
    # 추론이 느려지면 프레임 간격도 벌어진다. 허용 간격을 고정해두면 느린
    # 추론에서 트랙이 항상 끊겨, 모델 성능이 아니라 이 상수 때문에 실패한다.
    gap = C.SESSION_TRACK_GAP_S if gap_s is None else gap_s

    tracks: list[list[dict]] = []
    for d in sorted(dets, key=lambda x: x["timestamp_s"]):
        box = (d["x1"], d["y1"], d["x2"], d["y2"])
        placed = False
        for tr in tracks:
            last = tr[-1]
            if d["timestamp_s"] - last["timestamp_s"] > gap:
                continue
            last_box = (last["x1"], last["y1"], last["x2"], last["y2"])
            if iou(box, last_box) >= C.SESSION_TRACK_IOU:
                tr.append(d)
                placed = True
                break
        if not placed:
            tracks.append([d])
    return tracks


def sweep_sessions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    vids = df[df["source_type"] == "video"]
    if vids.empty:
        return pd.DataFrame(), pd.DataFrame()

    per_session: list[dict] = []
    for (model, mode, src), g in vids.groupby(["model", "prompt_mode", "source_id"]):
        dur = float(g["timestamp_s"].max())
        for t in C.SWEEP_THRESHOLDS:
            pos = g[g["has_det"] & (g["is_positive"] == 1) & (g["score"] >= t)]
            neg = g[g["has_det"] & (g["is_positive"] == 0) & (g["score"] >= t)]

            fire_t = None
            n_fired = 0
            for tr in build_tracks(pos.to_dict("records")):
                if len(tr) >= C.SESSION_HITS_REQUIRED:
                    n_fired += 1
                    ft = float(tr[C.SESSION_HITS_REQUIRED - 1]["timestamp_s"])
                    fire_t = ft if fire_t is None else min(fire_t, ft)

            # 네거티브 라벨도 같은 temporal filter 를 거친 "발화" 수로 센다.
            # 원시 박스 수를 세면 낮은 임계값에서 수천 개가 나와 의미가 없다.
            n_neg_fired = sum(1 for tr in build_tracks(neg.to_dict("records"))
                              if len(tr) >= C.SESSION_HITS_REQUIRED)

            per_session.append({
                "model": model,
                "prompt_mode": mode,
                "source_id": src,
                "threshold": t,
                "duration_s": round(dur, 1),
                "n_positive_frames": int(pos["frame_idx"].nunique()),
                "fired": int(fire_t is not None),
                "time_to_fire_s": round(fire_t, 2) if fire_t is not None else None,
                "success_within_window": int(fire_t is not None and fire_t <= C.SESSION_WINDOW_S),
                # 앱이 알림을 띄우는 횟수. 안경이 세션당 1개라면 1개를 넘는 만큼이
                # 오탐 후보다. 진짜 오탐인지는 렌더링을 봐야 안다.
                "n_fired_tracks": n_fired,
                "extra_positive_fires": max(0, n_fired - 1),
                # 진단용 — 네거티브 어휘가 얼마나 흡수하고 있는지
                "negative_fires_per_30s": round(n_neg_fired / dur * 30.0, 2) if dur > 0 else 0.0,
            })
    per_session_df = pd.DataFrame(per_session)

    rows: list[dict] = []
    for (model, mode, t), g in per_session_df.groupby(["model", "prompt_mode", "threshold"]):
        ok = int(g["success_within_window"].sum())
        times = g.loc[g["success_within_window"] == 1, "time_to_fire_s"]
        rows.append({
            "model": model,
            "prompt_mode": mode,
            "threshold": t,
            "n_sessions": int(len(g)),
            "n_success": ok,
            "session_success_rate": round(ok / len(g), 3),
            "median_time_to_fire_s": round(float(times.median()), 2) if len(times) else None,
            "mean_extra_positive_fires": round(float(g["extra_positive_fires"].mean()), 2),
            "mean_negative_fires_per_30s": round(float(g["negative_fires_per_30s"].mean()), 2),
        })
    return pd.DataFrame(rows), per_session_df


# ── 메인 ────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=Path("../runs/0a"))
    ap.add_argument("--data", type=Path, default=Path("../data"),
                    help="no_glasses.txt (네거티브 컨트롤 목록) 을 찾을 위치")
    args = ap.parse_args()

    raw = args.run / "raw_detections.csv"
    if not raw.exists():
        raise SystemExit(f"없습니다: {raw.resolve()}\n먼저 run_detect 를 돌려주세요.")

    df = pd.read_csv(raw)
    df["has_det"] = df["score"].notna()
    df = add_score_ensemble(df)

    no_glasses = load_no_glasses(args.data)
    if no_glasses:
        print(f"네거티브 컨트롤 {len(no_glasses)}개 (안경 없는 소스): "
              f"{', '.join(sorted(no_glasses))}")
    else:
        print("네거티브 컨트롤 없음 — 모든 소스에 안경이 있다고 가정합니다.")

    img_sweep, per_image = sweep_images(df, no_glasses)
    ses_sweep, per_session = sweep_sessions(df)

    for name, d in (
        ("sweep_images.csv", img_sweep),
        ("per_image.csv", per_image),
        ("sweep_sessions.csv", ses_sweep),
        ("per_session.csv", per_session),
    ):
        if d is not None and not d.empty:
            d.to_csv(args.run / name, index=False, encoding="utf-8-sig")
            print(f"쓰기 → {args.run / name}  ({len(d)} 행)")

    lat = (df.drop_duplicates(["model", "prompt_mode", "source_id", "frame_idx"])
             .groupby("model")["latency_ms"].agg(["mean", "median", "max"]).round(1))
    print("\n=== 레이턴시 (ms, 데스크탑 RTX 3070 — 실기기 아님) ===")
    print(lat.to_string())

    if not per_image.empty:
        print("\n=== 1단계: 사진별 최고 positive 점수 ===")
        piv = per_image.pivot_table(index="source_id",
                                    columns=["model", "prompt_mode"],
                                    values="top_positive_score")
        print(piv.round(3).to_string())

        print("\n=== 1단계: 임계값별 검출 / 오탐 ===")
        print("  형식  임계값:검출수/안경있는사진  (FP=오탐수/안경없는사진)")
        for (model, mode), g in img_sweep.sort_values(
                ["model", "prompt_mode", "threshold"]).groupby(["model", "prompt_mode"]):
            line = "  ".join(
                f"{r.threshold:.2f}:{r.n_detected}/{r.n_with_glasses}"
                f"(FP{r.n_false_positive}/{r.n_without_glasses})"
                for r in g.itertuples())
            print(f"  {model:22s} {mode:22s} {line}")

        if per_image["condition"].nunique() > 1:
            print("\n=== 조건별 요약 (열화 시뮬레이션) ===")
            for (model, mode), g in per_image.groupby(["model", "prompt_mode"]):
                print(f"\n  [{model} / {mode}]")
                print(f"    {'조건':<10} {'검출@0.25':>10} {'검출@0.40':>10} "
                      f"{'있음 최저':>10} {'없음 최고':>10} {'간격':>8}")
                order = ["orig", "d1m", "d1_5m", "d2m", "d3m", "lowlight", "blur"]
                conds = sorted(g["condition"].unique(),
                               key=lambda c: order.index(c) if c in order else 99)
                for cond in conds:
                    c = g[g["condition"] == cond]
                    yes = c[c["has_glasses"] == 1]["top_positive_score"]
                    no = c[c["has_glasses"] == 0]["top_positive_score"]
                    if yes.empty:
                        continue
                    lo = float(yes.min())
                    hi = float(no.max()) if not no.empty else 0.0
                    print(f"    {cond:<10} {int((yes >= 0.25).sum()):>6}/{len(yes):<3} "
                          f"{int((yes >= 0.40).sum()):>6}/{len(yes):<3} "
                          f"{lo:>10.3f} {hi:>10.3f} {lo - hi:>+8.3f}")

        print("\n=== 1단계: 오탐 여유 (안경 없는 사진의 최고 positive 점수) ===")
        neg = per_image[per_image["has_glasses"] == 0]
        if neg.empty:
            print("  네거티브 컨트롤이 없습니다.")
        else:
            print(neg.pivot_table(index="source_id",
                                  columns=["model", "prompt_mode"],
                                  values="top_positive_score").round(3).to_string())
            yes = per_image[per_image["has_glasses"] == 1]
            print("\n  분리도 — 안경 있는 사진의 최저점 vs 안경 없는 사진의 최고점")
            for (model, mode), g in yes.groupby(["model", "prompt_mode"]):
                n = neg[(neg["model"] == model) & (neg["prompt_mode"] == mode)]
                lo = float(g["top_positive_score"].min())
                hi = float(n["top_positive_score"].max()) if not n.empty else 0.0
                gap = lo - hi
                mark = "분리됨" if gap > 0 else "겹침"
                print(f"  {model:22s} {mode:22s} 최저 {lo:.3f} / 최고 {hi:.3f}"
                      f"  간격 {gap:+.3f}  {mark}")

    if not ses_sweep.empty:
        print("\n=== 2단계: 세션 성공률 (15초 창) ===")
        print(ses_sweep.sort_values(["model", "prompt_mode", "threshold"]).to_string(index=False))

    print("\n주의: 정답 박스가 없으므로 박스가 실제로 안경 위에 있는지는")
    print(f"      {args.run / 'annotated'} 의 렌더링을 눈으로 확인해야 합니다.")


if __name__ == "__main__":
    main()
