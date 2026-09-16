# iOS — 내 안경 찾기

Android 앱과 같은 내용의 SwiftUI 앱. **2026-09-14 윈도우에서 작성했고 아직 한 번도 빌드하지 않았다.**
처음 빌드하면 컴파일 에러가 몇 개 나올 것으로 본다 (아래 "확인 필요" 목록).
맥에서 Claude Code 로 열어 에러를 보면서 고치는 게 가장 빠르다.

## 구조

```
ios/
  project.yml            XcodeGen 정의 (이게 원본. .xcodeproj 는 생성물이라 git 에 없음)
  Config/                빌드 설정. 광고 ID
  scripts/gen_strings.py Android strings.xml → iOS 문자열 카탈로그
  FindGlasses/
    App/        앱 진입점, 메인 화면
    Finder/     찾기 본체 — 카메라, 모델, 추적 (Android MainActivity·Tracker 등의 이식)
    UI/         오버레이, 튜토리얼, 설정, 폭죽, 라이선스
    Services/   음성·진동, 광고, 광고 동의, 인앱결제(자리만)
    Resources/  문자열 17개 언어, 앱 아이콘, 라이선스 원문, (모델 — 직접 복사)
```

Android 파일과 1:1 로 대응한다. 로직을 고치면 양쪽을 같이 고친다.

| Android | iOS |
|---|---|
| CameraX | AVFoundation (`Camera.swift`) |
| SensorManager 회전벡터 | CoreMotion (`Motion.swift`) |
| ONNX Runtime Android + NNAPI | ONNX Runtime iOS + Core ML (`YoloDetector.swift`) |
| TextToSpeech / Vibrator | AVSpeechSynthesizer / Core Haptics (`Feedback.swift`) |
| 벨소리 모드 확인 | 오디오 세션 `.ambient` — 무음 스위치를 자동으로 따른다 |
| 앱 내 언어 선택 | iOS 설정 → 앱 → 언어 (설정 화면에서 바로 연다) |
| AdMob + UMP | 같은 SDK 의 iOS 판 |
| Play Billing (자리만) | StoreKit 2 (자리만) |

## 맥에서 처음 돌리기

1. **Xcode** 설치 (App Store). 용량이 크니 공간 확보
2. **XcodeGen** 설치
   ```bash
   brew install xcodegen
   ```
3. 저장소 받기 (이미 있으면 `git pull`)
4. **모델 파일 복사** — 50MB 라 git 에 없다. 윈도우의
   `android/app/src/main/assets/yolo-world-s-v2.onnx` 를 맥의
   `ios/FindGlasses/Resources/yolo-world-s-v2.onnx` 로 옮긴다 (클라우드 드라이브·USB 등).
   맥에서 새로 만들려면 `poc/scripts/export_android_model.py` (uv 환경 필요).
5. 프로젝트 생성 후 열기
   ```bash
   cd ios && xcodegen && open FindGlasses.xcodeproj
   ```
   처음 열면 Swift 패키지(ONNX Runtime, Google Mobile Ads, UMP)를 받느라 시간이 걸린다.
6. **서명**: 타깃 FindGlasses → Signing & Capabilities → Team 선택
7. **아이폰 연결**: 케이블로 연결 → 아이폰 설정 → 개인정보 보호 및 보안 → 개발자 모드 켜기
8. Xcode 위쪽에서 기기를 아이폰으로 고르고 ▶ 실행

시뮬레이터에는 카메라가 없어 찾기 기능은 실기기에서만 확인할 수 있다.

## 확인 필요 (윈도우에서 확인할 수 없었던 것)

컴파일
- [ ] ONNX Runtime 패키지의 모듈 이름 — 코드는 `import onnxruntime_objc` 로 썼다
- [ ] Google Mobile Ads 12.x 의 Swift 이름 — `MobileAds.shared`, `BannerView`, `InterstitialAd.load(with:request:)`,
      `FullScreenContentDelegate` 로 썼다. 버전에 따라 `GAD` 접두사가 붙은 옛 이름일 수 있다
- [ ] UMP 3.x 의 Swift 이름 — `ConsentInformation.shared`, `ConsentForm.loadAndPresentIfRequired(from:)`
- [ ] 동시성 경고/에러 — `SWIFT_STRICT_CONCURRENCY: minimal` 로 두었다

실기기
- [ ] **자이로 방향**: 폰을 위로 돌리면 네모가 아래로 가야 한다. 반대면 `Motion.transpose = true`
- [ ] **초점거리**: 폰을 옆으로 돌렸을 때 네모가 안경을 따라가는 양이 맞는지. 모자라거나 넘치면
      `Camera.focalPx` (videoFieldOfView 기반) 확인
- [ ] 분석 프레임이 세로로 오는지 (`videoRotationAngle = 90`). 가로로 오면 네모가 90도 틀어진다
- [ ] Core ML 이 이 모델(dynamic 입력)을 받는지 — 로그에 `CoreML 실패, CPU 로 전환` 이 뜨는지, 속도 비교
- [ ] 음성: 무음 스위치를 켜면 조용해지는지, 한국어 음성이 나오는지
- [ ] 진동: 톡 / 톡톡 / 톡톡톡 이 구분되는지
- [ ] 동의 창 → 광고 시작 순서, 찾았어요 → 폭죽 → 전면 광고

출시 전
- [ ] `Config/Secrets.xcconfig` 에 실제 AdMob iOS ID (Android 와 다른 앱으로 등록)
- [ ] `SKAdNetworkItems` 전체 목록 — AdMob iOS 빠른 시작 가이드에서 받아 `project.yml` 에 추가
- [ ] App Store Connect: 앱 개인정보 보호 라벨 (광고 SDK 수집 항목), 스크린샷
- [ ] 광고 추적 권한(ATT)은 쓰지 않았다. 필요하면 추가 — 쓰면 권한 창이 하나 더 뜬다
- [ ] 인앱결제 StoreKit 2 연결 (`Purchases.swift`)

## 문자열

Android `values*/strings.xml` 이 원본이다. 문구를 바꾸면 Android 를 고치고
```bash
python ios/scripts/gen_strings.py
```
카메라 권한 문구(iOS 전용)는 스크립트 안에 있다.
