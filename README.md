# find-glasses

**안경을 벗어서 안경이 보이지 않을 때, 스마트폰 카메라가 대신 안경을 찾아
큰 방향표시·음성·진동으로 알려주는 온디바이스 앱.**

## 상태

Phase 0 — 모델 기술검증 (Go/No-Go 판정 전)

전체 제품 개발은 아래 질문에 만족스러운 답이 나온 뒤에 진행한다.

> 안경을 쓰지 않은 사용자가 스마트폰으로 방을 천천히 훑었을 때,
> 15초 이내에 안경을 찾아내는 세션 성공률이 충분히 높은가?

## 핵심 제약

- custom training / 데이터셋 제작 없음 (pretrained zero-shot만 사용)
- 서버 inference / API 없음, 100% on-device
- 회원가입 없음
- 무료 + 광고
- UI는 사용자가 안경을 쓰지 않은 상태를 전제로 설계

## 문서

- [제품/기술 기획서](docs/product-plan.md)

## 구조 (예정)

```
docs/      기획·리서치 문서
poc/       Phase 0 파이썬 벤치마크 (모델 비교)
android/   Phase 1 Android Native PoC
```

## 라이선스

이 저장소의 코드는 [GNU AGPL-3.0](LICENSE) 으로 배포한다.

앱에 포함된 모델 가중치(YOLO-World v2, `yolov8s-worldv2`)는 Ultralytics 가
AGPL-3.0 으로 배포한 것이다. 원 연구·가중치는 Tencent AI Lab (GPL-3.0).
그 밖의 부품 고지는 앱 안의 "오픈소스 라이선스" 화면에 있다.

### 추가 허가 (AGPL-3.0 제7조)

As an additional permission under section 7 of the GNU AGPL-3.0, the copyright
holders of this repository's own code give you permission to convey the
combined work that links or bundles this code with the Google Mobile Ads SDK,
the Google User Messaging Platform SDK and the Google Play Billing Library
(and their dependencies distributed by Google), without the corresponding
source of those libraries being covered by this License.

이 추가 허가는 **이 저장소의 저작권자가 작성한 코드에만** 적용된다.
Ultralytics 가 배포한 모델 가중치에는 적용되지 않는다.
