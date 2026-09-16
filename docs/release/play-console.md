# Play Console 입력 초안

> 2026-09-13 작성. Play Console 화면 문구와 항목은 바뀔 수 있으니 입력할 때 화면 기준으로 맞춘다.
> 법률 자문이 아니다.

## 0. 올리기 전 준비 (사용자)

1. **업로드 키 만들기** — 저장소 밖 `D:/AppCompany/keys` 에 keytool 로 만든다. 비밀번호는 직접 입력, 백업.
2. **서명 정보** — 같은 폴더의 서명 파일에 둔다 (형식은 `android/app/build.gradle.kts` 주석).
   AdMob ID 는 `android/local.properties` 에 (git 에 안 올라감)
   ```
   admob.appId=ca-app-pub-...~...
   admob.bannerId=ca-app-pub-.../...
   admob.interstitialId=ca-app-pub-.../...
   ```
3. 서명 빌드: `android/build-signed.bat` — 서명 파일은 이 스크립트가 돌 때만 열린다
   → `android/app/build/outputs/bundle/release/app-release.aab`
   올릴 때마다 `versionCode` 를 1 씩 올린다
4. Play Console 에서 **Play App Signing** 사용 (기본값). 위 키는 업로드 키가 된다.
5. AdMob 콘솔 → 개인정보 보호 및 메시지 → **GDPR 메시지** 생성 (없으면 동의 창이 안 뜬다)
6. 저장소 공개 + GitHub Pages 켜기 (Settings → Pages → Branch `main`, 폴더 `/docs`)
   → 개인정보처리방침 주소 `https://myaune.github.io/find-my-glasses/privacy/`

## 1. 앱 기본 정보

| 항목 | 값 |
|---|---|
| 패키지 | `com.myaune.findglasses` (변경 불가) |
| 앱 이름 (한국어) | 내 안경 찾기 |
| 앱 이름 (영어, 기본) | Find My Glasses |
| 앱 / 게임 | 앱 |
| 무료 / 유료 | 무료 |
| 카테고리 | 도구 (Tools) |
| 광고 포함 | **예** |
| 인앱 상품 | 예 (광고 제거) — 결제 연결 후 |

## 2. 데이터 보안 (Data safety)

Play 의 "수집" 은 **기기 밖으로 전송하는 것**을 뜻한다. 카메라 영상은 기기 안에서만 처리하고
전송하지 않으므로 수집이 아니다. 앱 자체는 아무것도 보내지 않고, 광고 SDK 만 보낸다.

Google 의 AdMob 데이터 공개 안내(<https://developers.google.com/admob/android/privacy/play-data-disclosure>)
기준, Google Mobile Ads SDK 가 **자동으로 수집·공유**하는 항목:

| 데이터 | 목적 | 전송 암호화 | 선택 가능 |
|---|---|---|---|
| IP 주소 (대략적 위치 추정에 쓰일 수 있음) | 광고, 분석, 사기 방지 | 예 | 아니오 |
| 앱 상호작용 (앱 실행, 탭, 광고 조회) | 광고, 분석, 사기 방지 | 예 | 아니오 |
| 진단 (실행 시간, 응답 없음 비율, 전력 사용) | 광고, 분석, 사기 방지 | 예 | 아니오 |
| 기기 또는 기타 ID (광고 ID, 앱 세트 ID) | 광고, 분석, 사기 방지 | 예 | 아니오 |

- 위 표의 IP 주소를 Play 양식의 어느 칸(예: 위치 → 대략적 위치)에 넣을지는 **입력 시점의 Google 안내를 다시 확인**한다
- 사용자 데이터 삭제 요청: 앱이 보관하는 데이터가 없음
- 광고 제거 결제를 붙이면 **구매 기록** 항목이 추가될 수 있다 (Play Billing 안내 확인)

## 3. 콘텐츠 등급 (IARC 설문)

- 폭력, 성적 콘텐츠, 욕설, 약물, 도박: 없음
- 사용자 간 소통·콘텐츠 공유: 없음
- 위치 공유: 없음
- 디지털 상품 구매: 있음 (광고 제거) — 결제 연결 후
- 광고: 있음

## 4. 대상 연령

**18세 이상 권장.** 13세 미만을 대상에 넣으면 가족 정책(광고 SDK 인증, 추가 심사)이
붙는다. 안경을 찾는 앱이라 주 사용자는 성인이다.

## 5. 기타 선언

- 뉴스 앱: 아니오
- 정부 앱: 아니오
- 금융 기능: 없음
- 건강 앱: 아니오
- 광고 ID 사용: 예 (AdMob) — 목적: 광고, 분석
- 카메라 권한: 안경을 찾기 위한 실시간 영상 처리, 기기 안에서만

## 6. 스토어 등록정보

### 한국어

**앱 이름** (최대 30자)
```
내 안경 찾기
```

**간단한 설명** (최대 80자)
```
안경을 벗으면 안경이 안 보이죠. 폰 카메라가 대신 찾아서 알려드려요.
```

**자세한 설명** (최대 4000자)
```
안경을 벗어두고 어디 뒀는지 모를 때, 폰을 들고 방을 천천히 비춰보세요.
카메라가 안경을 찾으면 큰 네모와 화살표, 음성, 진동으로 위치를 알려드려요.

● 안경을 안 쓴 눈으로도 보이게
큰 표시와 색(노랑 → 연두 → 초록), 음성 안내, 진동으로 알려줘요.

● 기기 안에서만 처리
카메라 영상은 폰 밖으로 나가지 않아요. 회원가입도 없어요.

● 이럴 때 잘 찾아요
대충 어디쯤 뒀는지 알 때, 가까운 거리에서 둘러볼 때 가장 잘 찾아요.
단색 바닥이나 책상 위에서는 잘 보이고, 무늬가 복잡한 곳에서는 조금 더 가까이 가주세요.

● 부가 기능 (실험)
열쇠·휴대폰·리모컨도 찾아볼 수 있어요. 아직 충분히 시험하지 않은 기능이에요.

● 오픈소스
소스 코드가 공개되어 있어요 (AGPL-3.0).
```

### English

**App name**
```
Find My Glasses
```

**Short description**
```
Can't see your glasses without your glasses? Your phone camera finds them.
```

**Full description**
```
Took your glasses off and can't find them? Slowly sweep your phone around the room.
When the camera spots your glasses, a big box, arrows, voice and vibration show you where.

● Made for eyes without glasses
Big markers that change color (yellow → green), voice guidance and vibration.

● Everything stays on your device
Camera video never leaves your phone. No sign-up.

● Works best when
You roughly know where you left them and look around up close.
Glasses stand out on plain floors and desks; on busy patterns, move a little closer.

● Bonus (experimental)
Try finding keys, phones and remotes too. Not fully tested yet.

● Open source
The source code is public (AGPL-3.0).
```

## 7. 그래픽 (나중에)

- 앱 아이콘 512×512 PNG
- 그래픽 이미지 1024×500
- 휴대전화 스크린샷 최소 2장
