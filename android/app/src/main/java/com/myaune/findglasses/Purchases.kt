package com.myaune.findglasses

import android.app.Activity

/**
 * 광고 제거 IAP (non-consumable). 기획서 14절은 $1.99 였고 약 $1.5 로 낮추기로 했다 (2026-09-13).
 *
 * 문구는 "광고 없애기" 가 주이고 개발자 응원은 한 줄만 곁들인다. 감성에 기대지 않는다.
 *
 * 지금은 구조만 있다. 설정의 광고 없애기 카드 / 구매 복원과 결과 처리는 다 연결돼 있고,
 * 실제 결제만 [PlaceholderPurchases] 가 "아직 준비 중" 으로 막는다.
 *
 * 가격 문자열은 코드에 박지 않는다. 스토어가 국가별 통화·가격으로 준다
 * (Play: ProductDetails.oneTimePurchaseOfferDetails.formattedPrice). 국가별 가격은
 * Play Console 에서 정한다.
 *
 * 붙일 때 할 일
 *   - Play Console 에 상품 등록 (non-consumable, 예: remove_ads), 국가별 가격
 *   - com.android.billingclient:billing-ktx 추가, 이 인터페이스를 구현
 *   - 앱 시작 시 queryPurchasesAsync 로 보유 여부를 확인 → [adFree]
 *   - 구매 확인(acknowledge) 을 3일 안에 하지 않으면 자동 환불된다
 *   - iOS 는 StoreKit. 구매 복원 버튼이 없으면 심사에서 리젝된다
 */
interface Purchases {

    /** 광고 제거를 이미 샀는가 */
    val adFree: Boolean

    /** 스토어가 준 현지 가격 ("$1.99", "₩2,500" 등). 모르면 null → 가격 없이 표시 */
    fun removeAdsPrice(onPrice: (String?) -> Unit)

    fun buyRemoveAds(activity: Activity, onResult: (Result) -> Unit)

    fun restore(onResult: (Result) -> Unit)

    enum class Result {
        PURCHASED,
        RESTORED,
        NOTHING_TO_RESTORE,
        CANCELLED,
        /** 결제를 쓸 수 없음 (아직 미구현, 스토어 미연결 등) */
        UNAVAILABLE,
    }
}

/** 실제 결제를 붙이기 전까지 쓰는 자리 표시. 항상 UNAVAILABLE. */
class PlaceholderPurchases : Purchases {
    override val adFree = false

    override fun removeAdsPrice(onPrice: (String?) -> Unit) = onPrice(null)

    override fun buyRemoveAds(activity: Activity, onResult: (Purchases.Result) -> Unit) =
        onResult(Purchases.Result.UNAVAILABLE)

    override fun restore(onResult: (Purchases.Result) -> Unit) =
        onResult(Purchases.Result.UNAVAILABLE)
}
