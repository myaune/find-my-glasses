package com.myaune.findglasses

import android.app.Activity
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClient.BillingResponseCode
import com.android.billingclient.api.BillingClient.ProductType
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams

/**
 * 광고 제거 — Google Play 결제 (일회성 상품 [PRODUCT_ID]).
 *
 * 회원가입이 필요 없다. 구매는 폰에 로그인된 **Google 계정**에 묶이고, 같은 계정이면
 * 앱을 지웠다 깔거나 다른 폰에서도 [restore] (queryPurchasesAsync) 로 다시 찾는다.
 *
 * 구매 상태는 SharedPreferences 에 캐시해 앱을 켜자마자 광고를 끌지 정한다. 스토어에
 * 연결되면 실제 보유 여부로 다시 맞춘다 (환불되면 광고가 돌아온다).
 *
 * 서버가 없어 구매 영수증을 서버에서 검증하지 않는다. 광고 제거 같은 저가 상품에는
 * 흔한 선택이지만, 조작된 기기에서 우회될 수 있다.
 */
class GooglePlayPurchases(context: Context) : Purchases, PurchasesUpdatedListener {

    private val prefs = context.getSharedPreferences("purchases", Context.MODE_PRIVATE)
    private val main = Handler(Looper.getMainLooper())

    private val client = BillingClient.newBuilder(context.applicationContext)
        .setListener(this)
        .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
        .enableAutoServiceReconnection()
        .build()

    private var product: ProductDetails? = null
    private var pendingBuy: ((Purchases.Result) -> Unit)? = null
    private var onAdFreeChanged: ((Boolean) -> Unit)? = null

    private var connecting = false
    private val waiters = ArrayList<(Boolean) -> Unit>()

    override val adFree: Boolean get() = prefs.getBoolean(KEY_AD_FREE, false)

    override fun start(onAdFreeChanged: (Boolean) -> Unit) {
        this.onAdFreeChanged = onAdFreeChanged
        connect { ok -> if (ok) refreshOwned(null) }
    }

    override fun end() {
        pendingBuy = null
        onAdFreeChanged = null
        client.endConnection()
    }

    override fun removeAdsPrice(onPrice: (String?) -> Unit) {
        connect { ok ->
            if (!ok) onPrice(null) else loadProduct { onPrice(it?.let(::priceOf)) }
        }
    }

    override fun buyRemoveAds(activity: Activity, onResult: (Purchases.Result) -> Unit) {
        connect { ok ->
            if (!ok) return@connect onResult(Purchases.Result.UNAVAILABLE)
            loadProduct { pd ->
                if (pd == null) return@loadProduct onResult(Purchases.Result.UNAVAILABLE)
                val params = BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(pd)
                pd.oneTimePurchaseOfferDetailsList?.firstOrNull()?.offerToken?.let { params.setOfferToken(it) }
                pendingBuy = onResult
                val r = client.launchBillingFlow(
                    activity,
                    BillingFlowParams.newBuilder().setProductDetailsParamsList(listOf(params.build())).build(),
                )
                if (r.responseCode != BillingResponseCode.OK) {
                    pendingBuy = null
                    if (r.responseCode == BillingResponseCode.ITEM_ALREADY_OWNED) restore(onResult)
                    else onResult(Purchases.Result.UNAVAILABLE)
                }
            }
        }
    }

    override fun restore(onResult: (Purchases.Result) -> Unit) {
        connect { ok ->
            if (!ok) return@connect onResult(Purchases.Result.UNAVAILABLE)
            refreshOwned { owned ->
                onResult(if (owned) Purchases.Result.RESTORED else Purchases.Result.NOTHING_TO_RESTORE)
            }
        }
    }

    override fun onPurchasesUpdated(result: BillingResult, purchases: MutableList<Purchase>?) {
        main.post {
            val cb = pendingBuy
            pendingBuy = null
            when (result.responseCode) {
                BillingResponseCode.OK -> {
                    val owned = grant(purchases.orEmpty())
                    // 결제 대기(PENDING)면 아직 주지 않는다. 완료되면 다음 실행 때 반영된다.
                    cb?.invoke(if (owned) Purchases.Result.PURCHASED else Purchases.Result.CANCELLED)
                }
                BillingResponseCode.USER_CANCELED -> cb?.invoke(Purchases.Result.CANCELLED)
                BillingResponseCode.ITEM_ALREADY_OWNED -> if (cb != null) restore(cb) else refreshOwned(null)
                else -> {
                    Log.w(TAG, "구매 실패: ${result.responseCode} ${result.debugMessage}")
                    cb?.invoke(Purchases.Result.UNAVAILABLE)
                }
            }
        }
    }

    /** 결제 완료된 광고 제거 구매가 있으면 권한을 주고, 확인(acknowledge)이 안 됐으면 한다. */
    private fun grant(list: List<Purchase>): Boolean {
        var owned = false
        for (p in list) {
            if (PRODUCT_ID !in p.products || p.purchaseState != Purchase.PurchaseState.PURCHASED) continue
            owned = true
            // 3일 안에 확인하지 않으면 자동 환불된다
            if (!p.isAcknowledged) {
                client.acknowledgePurchase(
                    AcknowledgePurchaseParams.newBuilder().setPurchaseToken(p.purchaseToken).build()
                ) { r ->
                    if (r.responseCode != BillingResponseCode.OK) Log.w(TAG, "구매 확인 실패: ${r.debugMessage}")
                }
            }
        }
        if (owned) setAdFree(true)
        return owned
    }

    /** 스토어에 실제 보유 여부를 묻는다 (복원·환불 반영) */
    private fun refreshOwned(onDone: ((Boolean) -> Unit)?) {
        client.queryPurchasesAsync(
            QueryPurchasesParams.newBuilder().setProductType(ProductType.INAPP).build()
        ) { r, list ->
            main.post {
                if (r.responseCode != BillingResponseCode.OK) return@post onDone?.invoke(adFree) ?: Unit
                val owned = grant(list)
                if (!owned) setAdFree(false)  // 환불·취소
                onDone?.invoke(owned)
            }
        }
    }

    private fun loadProduct(onDone: (ProductDetails?) -> Unit) {
        product?.let { return onDone(it) }
        val params = QueryProductDetailsParams.newBuilder().setProductList(
            listOf(
                QueryProductDetailsParams.Product.newBuilder()
                    .setProductId(PRODUCT_ID)
                    .setProductType(ProductType.INAPP)
                    .build()
            )
        ).build()
        client.queryProductDetailsAsync(params) { r, result ->
            main.post {
                if (r.responseCode != BillingResponseCode.OK) Log.w(TAG, "상품 조회 실패: ${r.debugMessage}")
                product = result.productDetailsList.firstOrNull()
                onDone(product)
            }
        }
    }

    private fun priceOf(pd: ProductDetails): String? =
        pd.oneTimePurchaseOfferDetailsList?.firstOrNull()?.formattedPrice
            ?: pd.oneTimePurchaseOfferDetails?.formattedPrice

    private fun setAdFree(v: Boolean) {
        if (v == adFree) return
        prefs.edit().putBoolean(KEY_AD_FREE, v).apply()
        onAdFreeChanged?.invoke(v)
    }

    private fun connect(then: (Boolean) -> Unit) {
        if (client.isReady) return then(true)
        waiters += then
        if (connecting) return
        connecting = true
        client.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(r: BillingResult) {
                main.post {
                    connecting = false
                    val ok = r.responseCode == BillingResponseCode.OK
                    if (!ok) Log.w(TAG, "결제 연결 실패: ${r.responseCode} ${r.debugMessage}")
                    val list = waiters.toList()
                    waiters.clear()
                    list.forEach { it(ok) }
                }
            }

            override fun onBillingServiceDisconnected() {
                // enableAutoServiceReconnection 이 다음 호출 때 다시 붙인다
            }
        })
    }

    companion object {
        private const val TAG = "Purchases"

        /** Play Console 에 등록한 일회성 상품 ID */
        const val PRODUCT_ID = "remove_ads"

        private const val KEY_AD_FREE = "ad_free"
    }
}
