package com.myaune.findglasses

import android.app.Activity
import android.util.Log
import com.google.android.ump.ConsentInformation
import com.google.android.ump.ConsentRequestParameters
import com.google.android.ump.UserMessagingPlatform

/**
 * 광고 동의 (Google UMP). 유럽 등 동의가 필요한 지역에서만 창이 뜬다.
 *
 * 광고는 [canRequestAds] 가 true 가 된 뒤에만 초기화·요청한다. 지난 실행에서 받은
 * 동의가 있으면 바로 true 라 기다리지 않는다.
 *
 * 어떤 문구를 띄울지는 AdMob 콘솔 → 개인정보 보호 및 메시지 에서 정한다.
 * 거기서 메시지를 만들지 않으면 창이 뜨지 않는다.
 */
class Consent(private val activity: Activity) {

    private val info: ConsentInformation = UserMessagingPlatform.getConsentInformation(activity)

    val canRequestAds: Boolean get() = info.canRequestAds()

    /** 설정에 "광고 개인정보 설정" 을 보여야 하는가 (동의 지역 사용자) */
    val privacyOptionsRequired: Boolean
        get() = info.privacyOptionsRequirementStatus ==
            ConsentInformation.PrivacyOptionsRequirementStatus.REQUIRED

    /** @param onCanRequestAds 광고를 요청해도 될 때. 여러 번 불릴 수 있다. */
    fun gather(onCanRequestAds: () -> Unit) {
        info.requestConsentInfoUpdate(
            activity,
            ConsentRequestParameters.Builder().build(),
            {
                UserMessagingPlatform.loadAndShowConsentFormIfRequired(activity) { err ->
                    if (err != null) Log.w(TAG, "동의 창: ${err.message}")
                    if (info.canRequestAds()) onCanRequestAds()
                }
            },
            { err ->
                Log.w(TAG, "동의 정보 갱신 실패: ${err.message}")
                if (info.canRequestAds()) onCanRequestAds()
            },
        )
        // 지난 실행의 동의로 이미 가능하면 기다리지 않는다
        if (info.canRequestAds()) onCanRequestAds()
    }

    fun showPrivacyOptions() {
        UserMessagingPlatform.showPrivacyOptionsForm(activity) { err ->
            if (err != null) Log.w(TAG, "개인정보 옵션: ${err.message}")
        }
    }

    companion object {
        private const val TAG = "Consent"
    }
}
