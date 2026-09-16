# Phase 1 — 실기기 측정 앱

기획서 17절의 Phase 1. **제품이 아니다.** 카메라 → 추론 파이프라인만 돌리고
숫자를 남기는 측정 도구다. 제품 UI(굵은 네모 + 화살표 + 음성 + 진동)는
Phase 2 에서 만든다.

## 답해야 할 질문

Phase 0 에서 못 답한 것들이다 (`docs/phase0-results.md` 4절).

| | 왜 실기기여야 하나 |
|---|---|
| **추론 시간** | 가장 큰 미지수. 데스크탑 CPU 3.1초, RTX 3070 289ms. 폰은 모름 |
| NNAPI vs CPU | 어느 실행 프로바이더가 빠른지는 칩마다 다르다 |
| 영상 프레임 recall | 사진 100% vs 영상 25%. 실사용은 영상이다 |
| 세션 발화 시각 | 자이로 보상을 넣은 상태로는 처음 재본다 |

## 대상 기기

- **Redmi Note 13 4G** (`23129RAA4G`) — Snapdragon 685, Adreno 610, Hexagon DSP 686
- Cortex-A73 ×4 @2.8GHz + A53 ×4. 2016년 설계 코어다. 바닥 기준으로 삼는다

## 준비

### 1. 빌드 환경

```powershell
cd D:\AppCompany\find-glasses\android
. .\env.ps1
```

`env.ps1` 이 처리하는 것:
- Gradle 캐시를 D 로 (C 가 512GB SSD 라 여유가 없다)
- **Avast Web Shield 우회** — Java 는 Windows 인증서 저장소가 아니라 자체
  cacerts 를 본다. Avast 루트를 넣은 복사본을 `JAVA_TOOL_OPTIONS` 로 물린다.
  이게 없으면 Maven/Google 저장소 접속이 전부 실패한다

### 2. 폰 설정

1. **설정 → 휴대전화 정보 → MIUI 버전** 을 7번 연타 → 개발자 옵션 활성화
2. **설정 → 추가 설정 → 개발자 옵션 → USB 디버깅** 켜기
3. USB 로 연결, 폰에 뜨는 "USB 디버깅 허용" 승인

```powershell
adb devices        # 기기가 보이면 성공
```

### 3. 설치 + 모델 밀어넣기

```powershell
.\install.ps1
```

수동으로 하려면:

```powershell
adb install -r app\build\outputs\apk\debug\app-debug.apk
adb shell mkdir -p /sdcard/Android/data/com.myaune.findglasses/files
adb push ..\runs\0b\gdino-tiny-eyeglasses-fp16-iofp32.onnx `
  /sdcard/Android/data/com.myaune.findglasses/files/
```

**모델은 APK 에 넣지 않는다.** 124.6MB 라 빌드·설치가 느려지고, 측정 단계에서는
해상도를 바꿔가며 모델을 자주 교체하기 때문이다. 출시 앱(Phase 2)은 기획서
3절대로 APK 에 번들한다 — 코드는 파일 경로 한 줄 차이다.

## 쓰는 법

앱을 켜면 프리뷰 아래에 숫자가 뜬다.

```
추론      412 ms  (평균 435)
전/후처리  38 / 12 ms
FPS       2.15
최고점수   0.712  (임계 0.4)
검출       1개
발화       5.2초  (1회)
프로바이더 NNAPI
기록       ● bench-20260911-224530.csv
```

| 버튼 | |
|---|---|
| 기록 시작/정지 | CSV 로 남기기 |
| 세션 초기화 | 트랙과 통계를 비우고 다시 시작 |
| NNAPI/CPU | 실행 프로바이더 전환 (모델 다시 로드) |
| 공유 | 마지막 로그를 공유 시트로 |

### 측정 순서 제안

1. 안경을 책상에 놓고 1m 쯤 떨어져 앱 실행
2. **NNAPI** 로 [기록 시작] → 천천히 훑기 30초 → [정지]
3. [NNAPI/CPU] 눌러 **CPU** 로 전환, 같은 동작 반복
4. 안경을 치우고 같은 방을 30초 훑기 (오탐 측정 — **이게 중요하다**)

4번을 꼭 해야 한다. Phase 0 에서 네거티브 컨트롤이 사진 2장뿐이라 "오탐
0" 의 근거가 약하다. 안경 없는 방을 훑은 로그가 그 구멍을 메운다.

## 로그 가져오기

서버로 보내지 않는다 (기획서 3절). 둘 중 편한 쪽으로.

```powershell
adb pull /sdcard/Android/data/com.myaune.findglasses/files/logs ..\runs\phase1
```

또는 앱의 **[공유]** 버튼 → 카톡으로 자기 자신에게.

### CSV 형식

```
# device=Xiaomi 23129RAA4G
# soc=... sdk=34
# provider=NNAPI model_bytes=130573169 threshold=0.4
# input_size=800 prompt=eyeglasses
elapsed_ms,infer_ms,pre_ms,post_ms,n_det,top_positive,best_score,fired,fire_count
```

`top_positive` 는 임계값을 넘지 못한 프레임에서도 기록된다. 나중에 임계값을
바꿔가며 다시 계산할 수 있게 하려는 것이다 — Phase 0 의 오프라인 스윕과 같은
방식이다.

## 구조

```
Meta.kt              모델에 구워진 프롬프트의 토큰 구간, 정규화 상수
Preprocess.kt        프레임 → 회전 보정 → 800×800 letterbox → NCHW 텐서
GlassesDetector.kt   ONNX Runtime 세션, 추론, 후처리
Tracker.kt           자이로 보상 temporal filter (기획서 9절)
MetricsLogger.kt     CSV
MainActivity.kt      CameraX 연결, 화면, 버튼
OverlayView.kt       박스 그리기
```

### 데스크탑과 맞춰야 하는 것

**전처리가 `poc/bench/detectors/gdino_onnx.py` 의 `_letterbox` 와 같아야 한다.**
가로세로비 유지, 긴 변을 800 에 맞춤, 남는 곳 0, 가운데 배치. 여기가 어긋나면
"폰에서 안 잡힌다" 가 모델 탓인지 전처리 탓인지 구분되지 않는다.

**후처리는 Kotlin 에서 직접 구현했다.** 데스크탑은 transformers 함수를 그대로
불렀지만 Kotlin 에는 없다. 계산은 이렇게 맞췄다.

```
클래스 점수 = max over (그 클래스의 토큰 자리) sigmoid(logit)
검출        = 클래스별 점수의 argmax 가 eyeglasses 인 쿼리
```

네거티브 어휘가 더 높으면 버린다. 이게 오탐을 거르는 핵심이다.

### 모델을 다시 익스포트하면

`Meta.kt` 의 토큰 구간도 같이 갱신해야 한다.

```powershell
cd ..\poc
. .\env.ps1
uv run python scripts\export_android_meta.py
```

출력된 구간을 `Meta.CLASSES` 에 반영한다.

## 알려진 근사

- **병진 이동을 보상하지 않는다.** 자이로는 회전만 준다. 걸어다니면 트랙이
  끊길 수 있다. 회전이 지배적이라는 가정이고, 틀리면 측정에서 드러난다.
- **화각을 65° 로 가정한다.** 기기에서 읽어오면 정확해진다 (`Tracker.setHfov`).
- **디버그 빌드는 JIT 최적화가 덜 걸린다.** 최종 레이턴시 수치는 release
  빌드로 다시 재야 한다.
