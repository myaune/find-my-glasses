package com.myaune.findglasses

import android.app.Activity

/**
 * 광고 제거 IAP (non-consumable). 기획서 14절은 $1.99 였고 약 $1.5 로 낮추기로 했다 (2026-09-13).
 *
 * 문구는 "광고 없애기" 가 주이고 개발자 응원은 한 줄만 곁들인다. 감성에 기대지 않는다.
 *
 * 구현은 [GooglePlayPurchases] (Play 결제, 상품 ID remove_ads). 가격 문자열은 코드에 박지
 * 않는다. 스토어가 국가별 통화·가격으로 준다. 국가별 가격은 Play Console 에서 정한다.
 */
interface Purchases {

    /** 광고 제거를 이미 샀는가 (마지막으로 확인한 값, 앱을 켜자마자 쓸 수 있다) */
    val adFree: Boolean

    /** 스토어에 연결해 실제 보유 여부를 확인한다. 바뀌면 [onAdFreeChanged] 로 알린다. */
    fun start(onAdFreeChanged: (Boolean) -> Unit)

    fun end()

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

    override fun start(onAdFreeChanged: (Boolean) -> Unit) = Unit

    override fun end() = Unit

    override fun removeAdsPrice(onPrice: (String?) -> Unit) = onPrice(null)

    override fun buyRemoveAds(activity: Activity, onResult: (Purchases.Result) -> Unit) =
        onResult(Purchases.Result.UNAVAILABLE)

    override fun restore(onResult: (Purchases.Result) -> Unit) =
        onResult(Purchases.Result.UNAVAILABLE)
}
