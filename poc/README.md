# Phase 0 — 모델 기술검증 벤치마크

기획서 11절의 Phase 0. 답해야 할 질문은 하나다.

> pretrained open-vocabulary detector 가 **얼굴 없이 놓여 있는 안경**을 잡는가?

트레이닝은 하지 않는다. pretrained zero-shot 만 쓴다.

## 환경

이 머신은 캐시를 전부 D 드라이브로 보내고 있고, Avast 의 HTTPS 검사 때문에
CA 번들을 따로 지정해야 한다. 새 터미널에서는 사용자 환경변수로 이미 잡히지만,
확실히 하려면 dot-source 한다.

```powershell
cd D:\AppCompany\find-glasses\poc
. .\env.ps1
```

| | |
|---|---|
| Python | 3.11.16 (uv 관리, `D:\AppCompany\.cache\uv-python`) |
| torch | 2.11.0+cu128 |
| GPU | RTX 3070 8GB — **추론 속도용. 학습에 쓰지 않는다** |
| HF 캐시 | `D:\AppCompany\.cache\hf` |

## 데이터

`data/` 는 .gitignore 에 있다 (집 내부 사진이라 커밋 금지).

```
data/images/        1단계 — 안경 사진
data/videos/        2단계 — 스윕 영상
data/no_glasses.txt 안경이 없는 소스 목록 (네거티브 컨트롤)
```

### 네거티브 컨트롤

**안경이 없는 사진을 반드시 섞는다.** 이게 없으면 "안경을 잡는가"만 알 수 있고
"안경이 없는데도 있다고 하는가"를 모른다. 오탐은 기획서 11절 Go/No-Go 기준의
절반을 차지한다.

`data/no_glasses.txt` 에 파일명을 한 줄에 하나씩 적으면, 해당 소스는 검출률
집계에서 빠지고 대신 오탐 측정에 쓰인다.

### 1단계 — 사진

목적은 통계가 아니라 **"아예 못 잡는지"** 확인이다. 그래서 쉬운 조건부터 찍는다.
어려운 조건에서 실패하면 모델 탓인지 사진 탓인지 구분이 안 된다.

- 얼굴 없이 안경만
- 거리 0.5~1m, 밝은 곳
- 바닥면을 바꿔가며: 책상 / 천(이불·소파) / 마루·타일

### 2단계 — 영상 (1단계 통과 시에만)

폰 들고 방을 실제 쓸 때처럼 천천히 훑으며 30초 녹화. 영상당 안경이 한 번은
화면에 들어오게. 2.5 FPS 로 샘플링해 사진과 같은 파이프라인에 태운다.

## 실행

### 0a — FP32 상한선

```powershell
uv run python -m bench.run_detect --data ..\data --out ..\runs\0a
uv run python -m bench.analyze --run ..\runs\0a
```

`run_detect` 는 **추론을 한 번만** 돈다. 임계값 0.03 으로 원시 검출을 전부
CSV 에 남기고, 스윕은 `analyze` 가 그 CSV 만 보고 계산한다. 임계값마다
재추론하지 않는다.

### 산출물

| 파일 | 내용 |
|---|---|
| `raw_detections.csv` | 원시 검출 전체 (박스·점수·라벨·레이턴시) |
| `models.csv` | 모델별 파라미터 크기·라이선스·로드 시간 |
| `per_image.csv` | 사진별 최고 positive / negative 점수, 안경 유무 |
| `sweep_images.csv` | 임계값별 검출률(recall) 과 오탐률(fp_rate) |
| `per_session.csv` | 영상별 발화 시점·트랙 수 |
| `sweep_sessions.csv` | 임계값별 **세션 성공률** |
| `annotated/` | 박스를 그린 이미지 |

## 측정 방식

프레임 recall 이 아니라 **세션 성공률**로 잰다 (기획서 11절). 프레임 recall 이
낮아도 스윕 중 20~40회 시도하면 실사용에서는 성공하기 때문이다.

세션 판정은 기획서 9절의 temporal filter 를 흉내낸다 — 1초 이내 간격으로
IoU 0.1 이상 겹치는 positive 검출이 3회 쌓이면 발화. 15초 안에 발화하면 성공.

**한계 두 가지를 알고 봐야 한다.**

1. 실제 앱은 자이로로 카메라 모션을 보상한 좌표계에서 association 한다.
   오프라인 영상에는 자이로가 없어 화면 좌표 IoU 로만 묶으므로, 여기 숫자는
   실제보다 **보수적으로** 나올 수 있다.
2. 정답 박스가 없다. 박스가 실제로 안경 위에 있는지, 발화가 진짜인지 오탐인지는
   `annotated/` 렌더링을 **눈으로** 확인해야 한다. 숫자만 보면 안 된다.

## 프롬프트

기획서 5절.

```
positives  glasses / eyeglasses / spectacles / a pair of eyeglasses
negatives  keys / phone / scissors / pen / remote control / cup
```

네거티브는 항상 같이 투입한다. 단일 클래스 open-vocab 은 오탐이 심해서
경쟁 클래스를 넣어야 줄어든다.

### 함정 — Grounding DINO 의 text_threshold

Grounding DINO 는 박스 임계값과 별개로, **어떤 텍스트 토큰을 그 박스의 라벨에
넣을지** 정하는 임계값을 따로 받는다. 이걸 박스 임계값과 같이 낮게 주면 약하게
걸린 토큰까지 전부 이어붙어 이런 라벨이 나온다.

```
"glasses keys phone scissors pen remote control cup"  0.19
```

여기에 `glasses` 가 들어있다고 안경 검출로 세면 검출률이 통째로 오염된다.
`--text-threshold` 를 0.25 로 두고, 네거티브 어휘가 섞인 라벨은 양성에서
제외한다 (`bench/detectors/base.py:match_positive`).

앙상블은 모델에 따라 방식이 다르다.

| 모드 | 방식 | 적용 |
|---|---|---|
| `ensemble_embed` | 텍스트 임베딩 4개를 평균해 질의 1개로 | **OWLv2 만** |
| `ensemble_score` | 개별 4종 결과의 max 를 취함 (추가 추론 없음) | 전 모델 |

Grounding DINO 는 텍스트가 인코더 전 단계에 걸쳐 cross-attention 으로 융합되는
구조라, 텍스트 임베딩을 사후에 평균내는 방식이 성립하지 않는다. 그래서 스코어
레벨로 대신하고 결과에도 그렇게 표기한다.

## 모델

| 키 | HF ID | 라이선스 | 기본 |
|---|---|---|---|
| `grounding-dino-tiny` | IDEA-Research/grounding-dino-tiny | Apache-2.0 | ✅ |
| `owlv2-base` | google/owlv2-base-patch16-ensemble | Apache-2.0 | ✅ |
| `yolo-world` | yolov8s-worldv2.pt | GPL-3.0 (러너 ultralytics AGPL-3.0) | ❌ |

YOLO-World 는 폴백이라 기본 비활성이다. 쓰려면 `uv add ultralytics` 후
`--models yolo-world`. 데스크탑 벤치마크는 배포가 아니므로 라이선스 의무가
발생하지 않지만, 앱 탑재 시점에는 기획서 5·13절 판단이 그대로 적용된다.

## 0b — ONNX FP16

**Go/No-Go 판정은 0b 숫자로 한다.** 아직 미구현. FP32 에서 되는 것을 확인한
뒤에 붙인다. FP32 로 측정하고 배포 포맷에서 recall 이 반토막 나는 것이 고전적
함정이라 순서를 지킨다.

## 스모크 테스트

실제 안경 사진 없이 파이프라인과 좌표 보정을 확인한다.

```powershell
uv run python scripts\smoke.py
```

OWLv2 는 전처리에서 긴 변 기준 정사각 패딩을 하기 때문에, 모델이 내놓는
정규화 좌표를 원본으로 되돌리려면 `target_sizes` 에 `max(H, W)` 정사각을
넣어야 한다. 박스가 엉뚱한 곳에 찍히는 흔한 함정이라 위치를 아는 공개 테스트
이미지로 검증한다.
