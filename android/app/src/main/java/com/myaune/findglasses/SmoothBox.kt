package com.myaune.findglasses

import android.graphics.RectF
import kotlin.math.PI
import kotlin.math.abs

/**
 * 화면에 그리는 네모를 부드럽게 따라가게 한다. 표시용일 뿐 추적 좌표는 건드리지 않는다.
 *
 * 고정 lerp 를 쓰지 않은 이유: 폰을 돌리는 동안 자이로 보정이 매 센서 주기로
 * 들어오는데, 고정 lerp 는 그때도 뒤처져서 앵커링이 다시 어긋나 보인다.
 * 그래서 One Euro 필터(Casiez 2012)를 쓴다. 빠르게 움직일 때는 거의 그대로
 * 따라가고, 거의 멈춰 있을 때 생기는 점프(추론 결과 반영, 영상 추적 보정)만
 * 부드럽게 미끄러진다.
 *
 * 매 draw 마다 부른다. dt 를 실제 시간으로 넣어 화면 주사율과 무관하다.
 * 좌표 단위는 view 픽셀이고, 속도는 view 폭 기준으로 정규화한다.
 */
class SmoothBox {
    private val cx = OneEuro()
    private val cy = OneEuro()
    private val w = OneEuro()
    private val h = OneEuro()
    private var lastNs = 0L
    private val out = RectF()

    fun reset() {
        lastNs = 0L
    }

    fun update(target: RectF, viewWidth: Int, nowNs: Long): RectF {
        val scale = viewWidth.coerceAtLeast(1).toFloat()
        if (lastNs == 0L) {
            // 처음 나타날 때는 허공에서 날아오지 않고 그 자리에 뜬다
            cx.snap(target.centerX() / scale)
            cy.snap(target.centerY() / scale)
            w.snap(target.width() / scale)
            h.snap(target.height() / scale)
        } else {
            val dt = ((nowNs - lastNs) / 1e9f).coerceIn(1e-4f, 0.1f)
            cx.filter(target.centerX() / scale, dt)
            cy.filter(target.centerY() / scale, dt)
            w.filter(target.width() / scale, dt)
            h.filter(target.height() / scale, dt)
        }
        lastNs = nowNs
        val hw = w.value * scale / 2
        val hh = h.value * scale / 2
        out.set(cx.value * scale - hw, cy.value * scale - hh,
            cx.value * scale + hw, cy.value * scale + hh)
        return out
    }

    private class OneEuro {
        var value = 0f
            private set
        private var deriv = 0f

        fun snap(x: Float) {
            value = x
            deriv = 0f
        }

        fun filter(x: Float, dt: Float) {
            deriv += alpha(D_CUTOFF_HZ, dt) * ((x - value) / dt - deriv)
            val cutoff = MIN_CUTOFF_HZ + BETA * abs(deriv)
            value += alpha(cutoff, dt) * (x - value)
        }

        private fun alpha(cutoffHz: Float, dt: Float): Float {
            val tau = 1f / (2f * PI.toFloat() * cutoffHz)
            return 1f / (1f + tau / dt)
        }
    }

    companion object {
        /**
         * 멈춰 있을 때의 차단 주파수. 1.5Hz 면 점프가 약 0.3초에 걸쳐 미끄러진다.
         * 낮출수록 더 느긋하게 움직인다.
         */
        private const val MIN_CUTOFF_HZ = 1.5f

        /**
         * 속도에 따라 얼마나 빨리 따라갈지. 화면 폭/초 단위.
         * 1 폭/초로 돌리면 차단 주파수가 1.5 + 6 = 7.5Hz (지연 약 20ms).
         */
        private const val BETA = 6f

        private const val D_CUTOFF_HZ = 1f
    }
}
