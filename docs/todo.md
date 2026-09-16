# 할 일

> 2026-09-13 기준. 끝나면 지우지 말고 `[x]` 로 표시하고 날짜를 적는다.

## 출시 전 필수

### 라이선스 · 법무

앱에 들어가는 모델 가중치는 **Ultralytics 가 AGPL-3.0 으로 배포한 `yolov8s-worldv2`**
다. 기획서 5·13절은 원본 연구(Tencent AILab YOLO-World) 기준으로 GPL-3.0 이라
적었지만, 실제 파일은 Ultralytics 배포본이다. AGPL-3.0 은 GPL-3.0 보다 조건이 강하다.

- [x] 앱 내 오픈소스 라이선스 화면 (2026-09-13) — `LicensesActivity`, 튜토리얼 하단에서 진입
- [x] 라이선스 원문 번들 (2026-09-13) — `res/raw/`. AGPL 은 SPDX, Apache 는 apache.org, MIT 는 각 저장소
- [ ] **저장소를 공개로 전환** — 라이선스 화면의 소스 코드 링크가 지금은 비공개 저장소를 가리킨다
- [x] 저장소 루트에 `LICENSE` (AGPL-3.0) 추가 (2026-09-13) — README 에 광고·동의·결제 SDK 추가 허가(7조)
- [ ] **법률 검토** — 아래는 공개 자료로 확인한 것과 확인 못 한 것을 나눈 것이다. 변호사 판단이 아니다.

  **확인한 것**
  - 앱에서 조건이 붙는 남의 부품은 **모델 가중치 하나뿐**이다. 나머지(ONNX Runtime, AndroidX,
    Kotlin, Guava, CLIP 등)는 MIT·Apache 라 라이선스 화면에 고지만 하면 된다.
  - Ultralytics 는 ONNX 등 **어떤 형식으로 변환해도** AGPL-3.0 이 적용되고, 소스를 닫고 상업적으로
    쓰려면 Enterprise 라이선스를 사라고 명시한다
    ([License](https://www.ultralytics.com/license), [AGPL 안내](https://www.ultralytics.com/legal/agpl-3-0-software-license),
    [issue #6789](https://github.com/ultralytics/ultralytics/issues/6789)).
    → 앱 전체 소스를 AGPL 로 공개하면 이 조건은 충족된다.
  - AGPL/GPL 은 **돈 버는 것을 막지 않는다**. 광고·유료·IAP 모두 가능. 의무는 "소스를 받을 수 있게
    하는 것" 이다.
  - App Store: 2011년 VLC 가 저작권자 한 명의 이의로 App Store 에서 내려갔고, FSF 는 App Store
    이용약관이 GPL 과 충돌한다고 본다 ([FSF](https://www.fsf.org/blogs/licensing/vlc-enforcement)).
    **권리자(여기선 Ultralytics)가 문제 삼으면 내려갈 수 있다**는 선례다.

  **확인 못 한 것**
  1. **AGPL 앱 + 광고 SDK(소스 비공개)** — 구글 소스를 가져와 공개하라는 뜻이 아니다. GPL FAQ 는
     "GPL 부분과 합쳐 하나의 프로그램이 되면 전체를 GPL 로 낼 수 있어야 하고, 못 하면 합치면 안 된다"
     고 한다. 이를 풀어주는 예외는 **그 코드의 저작권자만** 붙일 수 있다 — 우리 코드는 우리가 붙이면
     되지만 모델 가중치는 Ultralytics 몫이다. Ultralytics 는 "앱 전체" 가 파생물이라고 주장한다.
     MIT 런타임이 읽는 데이터 파일(가중치)이 AdMob 과 "하나의 프로그램" 으로 묶이는지는 확인 못 했다.
     실제로 문제 삼은 사례도 찾지 못했다.
     → 할 일: `LICENSE` 추가할 때 우리 코드에 "AdMob SDK 와 함께 배포 허용" 추가 조항(AGPL 7조)을 붙인다.
  2. Ultralytics 가 "가중치 = 소프트웨어" 로 AGPL 을 거는 주장이 법원에서 어디까지 인정되는지.

  **선택지**
  - 그대로 공개 출시 (1번 위험을 안고 감)
  - Ultralytics Enterprise 라이선스 구매 → 가중치 조건이 사라지므로 1·2번 모두 해당 없음
  - Apache 모델로 교체 — 폰에서 돌아가는 후보가 지금은 없다 (`docs/phase0-results.md`)

### 개인정보

- [x] 개인정보처리방침 페이지 (2026-09-13) — `docs/privacy/index.html`. **GitHub Pages 켜야 URL 이 산다**
- [x] 카메라 영상 기기 내 처리 안내 (2026-09-13) — 개인정보처리방침·스토어 설명에 명시, 설정에 방침 링크
- [x] 광고 SDK 수집 항목 고지 (2026-09-13) — 개인정보처리방침
- [ ] Google Play **데이터 보안** 섹션 작성 — 초안 `docs/release/play-console.md`, 입력은 사용자
- [ ] Apple **앱 개인정보 보호** 라벨 작성
- [x] 광고 동의 (UMP 4.0.0) (2026-09-13) — `Consent.kt`. **AdMob 콘솔에서 GDPR 메시지 생성 필요**

### 수익화

- [x] AdMob 키 주입 구조 (2026-09-13) — `android/local.properties` 의 `admob.*` → release 에만. 디버그는 항상 테스트 ID
- [ ] 광고 제거 IAP (약 $1.5, non-consumable) — **구조만 있음** (2026-09-13): `Purchases.kt` 인터페이스 + `PlaceholderPurchases`, 설정의 "광고 없애기" 카드. Play Billing 구현체만 붙이면 된다. 국가별 가격은 Play Console
- [x] **구매 복원 버튼** (2026-09-13) — 응원 카드에 있음. 없으면 Apple 심사 리젝 (기획서 14절)

### 빌드 · 배포

- [x] 패키지 `com.myaune.findglasses`, 앱 아이콘(돋보기 속 안경), 스토어 아이콘 `docs/release/icon-512.png` (2026-09-13)

- [ ] 릴리스 서명 키 생성 · 보관 — 설정 구조는 있음 (2026-09-13) (`release.*` in local.properties). 키 생성은 사용자
- [x] AAB 빌드 확인 (2026-09-13) — 서명 없이 58MB. targetSdk 36 (2026-08-31 부터 새 앱 필수)
- [x] 개발자 도구 제거 (2026-09-13) — 화면에 BUILD_TAG 표시도 없어짐
- [ ] 릴리스 빌드로 **레이턴시 재측정** — 디버그 빌드는 JIT 최적화가 덜 걸린다
- [ ] Play Console 클로즈드 테스트 — **테스터 12명 × 14일** (기획서 15절)

## 결정 대기

- [x] **FP32 vs FP16** — FP32 로 확정 (2026-09-13). FP16 은 실기기에서 점수가 전혀 움직이지 않았다
- [ ] 화질 기본값 — 지금 416. 기기 성능을 보고 자동으로 고를지

## 기능

- [ ] ~~찾은 뒤 추론 줄이기~~ — 해봤다가 되돌림 (2026-09-13). 지금도 위치·보간 품질이 낮아 추론을 줄일 이유가 없다. 축하·광고 중 정지만 유지
- [ ] 햅틱 메트로놈 — 적정 스윕 속도로 유도 (기획서 4절). 지금은 음성만
- [x] 음성 / 진동 on·off + 앱 언어 설정 (2026-09-13) — 폰 무음·진동 모드도 따른다
- [ ] 열 스로틀링 후 FPS 재측정 — 오래 켜두면 떨어진다. 설계에는 그 하한을 써야 한다
- [ ] 화면 가장자리에 있는 안경의 자이로 보정 — 지금은 광축 기준 근사라 가장자리에서
      보정량이 조금 모자란다. 영상 추적이 성공하면 가려지는 문제라 우선순위 낮음

제외: 손전등 (2026-09-13 결정)

## 문서

- [ ] **기획서 v3 개정** — 실측으로 뒤집힌 것
  - 모델 Grounding DINO → YOLO-World s, 라이선스 GPL-3.0 → **AGPL-3.0**
  - 프롬프트 `glasses` → `a pair of eyeglasses`
  - 입력 해상도 960~1280 → 416 (사용자 선택 416/512/640)
  - 프레임 ≤500ms → 0.5~1.5 FPS
  - 자이로 앵커링: 보조 → 코어, 그리고 영상 추적(NCC) 추가
  - 스윕 속도 한계 ≤64°/s 고정 → FPS 따라 16~48°/s
  - temporal filter 3회 → 2회
  - 신뢰도 임계값 재조정 (0.16 / 0.30)
  - 탐지 거리 1.5~2m → 대비에 따라 다름
  - 모델 선정 관문: 데스크탑 CPU ≤60ms (`poc/scripts/latency_gate.py`)
- [ ] `docs/phase0-results.md` 에 Phase 1 결과 추가 (SD685 실측, GDINO 35초 → 폐기 경위)

## iOS

- [ ] 기획서 7절 — Swift + SwiftUI + AVFoundation. Android 가 안정되면 착수
- [ ] Core ML 변환 검토 — iPhone 은 Neural Engine 이 있어 ONNX Runtime CPU 보다 훨씬 빠를 가능성
