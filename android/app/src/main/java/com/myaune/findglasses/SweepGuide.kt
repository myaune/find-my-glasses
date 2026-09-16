package com.myaune.findglasses

import kotlin.math.abs
import kotlin.math.acos
import kotlin.math.min

/**
 * 스윕 속도 안내 (기획서 4절).
 *
 * 속도 제한은 UX 안내이면서 동시에 모션 블러로 인한 recall 저하를 막는 수단이다.
 *
 * 기획서는 2 FPS 를 전제로 ≤64°/s 를 계산했다. 실기기는 0.5~1.5 FPS 라
 * 한계가 훨씬 낮다. 프레임 간 화면이 겹쳐야 하므로, 화각 65도에서 프레임당
 * 회전이 화각의 절반을 넘지 않아야 한다.
 *
 *   한계 = 32도 × FPS
 *   1.5 FPS → 48°/s,  0.5 FPS → 16°/s
 *
 * 실제 FPS 를 받아 한계를 그때그때 계산한다. 고정값으로 두면 느린 기기에서
 * 안내가 무의미해진다.
 */
class SweepGuide {

    private var lastR: FloatArray? = null
    private var lastMs = 0L

    /** 최근 각속도 (도/초). 지수 이동 평균으로 떨림을 줄인다. */
    var degPerSec = 0f
        private set

    /** 현재 프레임 속도에서 허용되는 각속도 */
    var limitDegPerSec = 48f
        private set

    fun setFps(fps: Float) {
        if (fps > 0.05f) {
            limitDegPerSec = (HALF_FOV_DEG * fps).coerceIn(10f, 90f)
        }
    }

    fun reset() {
        lastR = null
        degPerSec = 0f
        tooFast = false
    }

    /** 현재 "너무 빠름" 상태 (히스테리시스 적용) */
    var tooFast = false
        private set

    /**
     * @return 너무 빠른가
     *
     * 한계 하나로 켜고 끄면 속도가 그 근처에서 흔들릴 때마다 상태가 튀어 음성이
     * 반복됐다. 켜는 기준(한계)과 끄는 기준(한계의 70%)을 달리 둔다.
     */
    fun onRotation(r: FloatArray, nowMs: Long): Boolean {
        val raw = measure(r, nowMs)
        tooFast = if (tooFast) raw > limitDegPerSec * EXIT_RATIO else raw > limitDegPerSec
        return tooFast
    }

    private fun measure(r: FloatArray, nowMs: Long): Float {
        val prev = lastR
        val prevMs = lastMs
        lastR = r.copyOf()
        lastMs = nowMs
        if (prev == null || nowMs <= prevMs) return degPerSec

        val dt = (nowMs - prevMs) / 1000f
        if (dt < 1e-3f) return degPerSec

        // 회전 델타의 각도 = acos((trace(M) - 1) / 2)
        var trace = 0f
        for (i in 0..2) {
            var s = 0f
            for (k in 0..2) s += r[k * 3 + i] * prev[k * 3 + i]
            trace += s
        }
        val cosA = ((trace - 1f) / 2f).coerceIn(-1f, 1f)
        val deg = Math.toDegrees(acos(cosA).toDouble()).toFloat()

        val inst = deg / dt
        degPerSec += (inst - degPerSec) * 0.25f      // EMA
        return degPerSec
    }

    companion object {
        /** 화각 65도의 절반. 프레임 간 화면이 겹치려면 이 이상 돌면 안 된다. */
        private const val HALF_FOV_DEG = 32f

        /** 한계의 이 비율 아래로 내려와야 "너무 빠름" 을 끈다 */
        private const val EXIT_RATIO = 0.7f
    }
}
