package com.myaune.findglasses

import android.graphics.Color

/**
 * 신뢰도 단계 (기획서 4절).
 *
 * 기획서의 임계값은 Grounding DINO 기준으로 쓰였는데, 채택한 YOLO-World 는
 * 점수 분포가 완전히 다르다. 실기기에서 실제 안경이 0.17~0.36 으로 나왔고
 * 데스크탑에서도 0.4 를 넘는 경우가 드물었다. 그 범위에 맞춰 다시 잡는다.
 *
 * 색 하나에 의존하지 않고 색 + 문구 + 펄스 속도로 3중 표기한다. 사용자가
 * 안경을 안 쓴 상태라는 게 이 앱의 전제다 (기획서 4절 접근성).
 */
enum class Confidence(
    val minScore: Float,
    val color: Int,
    val messageRes: Int,
    /** 펄스 한 주기 (ms). 짧을수록 급하게 깜빡인다. */
    val pulseMs: Int,
    /** 진동 세기 (1~255). 60 은 실기기에서 느껴지지 않았다. */
    val vibeAmplitude: Int,
) {
    LOW(0.00f, Color.rgb(255, 214, 0), R.string.conf_low, 1400, 140),
    MEDIUM(0.16f, Color.rgb(180, 220, 30), R.string.conf_medium, 900, 200),
    HIGH(0.30f, Color.rgb(40, 215, 90), R.string.conf_high, 520, 255);

    companion object {
        fun of(score: Float): Confidence =
            when {
                score >= HIGH.minScore -> HIGH
                score >= MEDIUM.minScore -> MEDIUM
                else -> LOW
            }
    }
}
