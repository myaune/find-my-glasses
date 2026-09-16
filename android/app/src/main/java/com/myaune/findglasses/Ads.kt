package com.myaune.findglasses

import android.app.Activity
import android.util.Log
import android.view.ViewGroup
import com.google.android.gms.ads.AdError
import com.google.android.gms.ads.AdListener
import com.google.android.gms.ads.AdRequest
import com.google.android.gms.ads.AdSize
import com.google.android.gms.ads.AdView
import com.google.android.gms.ads.FullScreenContentCallback
import com.google.android.gms.ads.LoadAdError
import com.google.android.gms.ads.MobileAds
import com.google.android.gms.ads.interstitial.InterstitialAd
import com.google.android.gms.ads.interstitial.InterstitialAdLoadCallback

/**
 * 광고 (기획서 14절).
 *
 *   하단 배너 고정
 *   [찾았다!] → 전면 광고        태스크 완료 직후, 성공했을 때만
 *   광고 제거 IAP 약 $1.5         자리만 있음 — Purchases.kt
 *
 * 광고 ID 는 build.gradle.kts 가 BuildConfig 로 넣는다. 디버그 빌드는 항상 구글
 * 테스트 ID, release 는 android/local.properties 의 실제 ID.
 *
 * 전면 광고에 빈도 제한을 두지 않는 이유는 기획서 14절에 있다 — 성공 시점에만
 * 걸려 있어 실패 후 재시도에는 뜨지 않고, 안경 분실 자체가 잦은 일이 아니다.
 */
class Ads(private val activity: Activity) {

    private var banner: AdView? = null
    private var interstitial: InterstitialAd? = null
    private var initialized = false

    /** 광고 제거 IAP 를 붙이면 이 값으로 전부 끈다. */
    var enabled = true

    fun init() {
        if (initialized) return
        initialized = true
        // 초기화는 네트워크를 타므로 백그라운드에서 돈다.
        MobileAds.initialize(activity) {
            Log.i(TAG, "MobileAds 초기화 완료")
        }
    }

    fun attachBanner(container: ViewGroup) {
        if (!enabled) {
            container.visibility = ViewGroup.GONE
            return
        }
        val v = AdView(activity).apply {
            adUnitId = BuildConfig.ADMOB_BANNER
            setAdSize(AdSize.BANNER)
            adListener = object : AdListener() {
                override fun onAdFailedToLoad(e: LoadAdError) {
                    Log.w(TAG, "배너 실패: ${e.message}")
                }
            }
        }
        container.removeAllViews()
        container.addView(v)
        v.loadAd(AdRequest.Builder().build())
        banner = v
    }

    /** 광고 제거를 샀을 때. 배너를 떼고 전면 광고도 버린다. */
    fun disable(container: ViewGroup) {
        enabled = false
        banner?.destroy()
        banner = null
        interstitial = null
        container.removeAllViews()
        container.visibility = ViewGroup.GONE
    }

    fun preloadInterstitial() {
        if (!enabled || interstitial != null) return
        InterstitialAd.load(
            activity, BuildConfig.ADMOB_INTERSTITIAL, AdRequest.Builder().build(),
            object : InterstitialAdLoadCallback() {
                override fun onAdLoaded(ad: InterstitialAd) {
                    interstitial = ad
                }

                override fun onAdFailedToLoad(e: LoadAdError) {
                    Log.w(TAG, "전면 광고 실패: ${e.message}")
                }
            },
        )
    }

    /**
     * 태스크 완료 직후에만 부른다 (기획서 14절).
     * @param onDone 광고가 닫히거나 없을 때 호출
     */
    fun showInterstitial(onDone: () -> Unit) {
        val ad = interstitial
        if (!enabled || ad == null) {
            onDone()
            preloadInterstitial()
            return
        }
        ad.fullScreenContentCallback = object : FullScreenContentCallback() {
            override fun onAdDismissedFullScreenContent() {
                interstitial = null
                preloadInterstitial()
                onDone()
            }

            override fun onAdFailedToShowFullScreenContent(e: AdError) {
                interstitial = null
                preloadInterstitial()
                onDone()
            }
        }
        ad.show(activity)
    }

    fun destroy() {
        banner?.destroy()
        banner = null
        interstitial = null
    }

    companion object {
        private const val TAG = "Ads"
    }
}
