package com.myaune.findglasses

import android.graphics.RectF
import kotlin.math.roundToInt
import kotlin.math.sqrt

/**
 * 정규상관(NCC) 패치 추적 — 이동까지 보정한다.
 *
 * 자이로는 자세만 주므로 이동을 보정할 수 없다. 가속도계를 두 번 적분하는
 * 방법은 바이어스 오차가 t² 로 커져 1~2초만 지나도 수십 cm 가 틀린다.
 *
 * 그리고 근거리에서는 시차가 크다. 몸을 10cm 옆으로 기울이면 가까운 안경과
 * 먼 배경이 다른 양만큼 움직이는데, 회전 보정은 거리를 모르니 이걸 표현할 수
 * 없다. 이 앱은 0.3~1m 를 다루므로 시차가 가장 큰 조건이다.
 *
 * 그래서 화면 전체가 아니라 **박스 주변 패치만** 추적한다. 그러면 회전·이동·
 * 시차가 한꺼번에 맞는다. 전역 움직임을 쓰면 배경이 지배해서 안경이 어긋난다.
 *
 * 놀고 있던 프레임을 쓴다. 추론이 0.7초 도는 동안 들어오는 20장을 그냥
 * 버리고 있었다. 추론이 끝나면 검출로 다시 고정하므로 추적 오차가 쌓이는
 * 구간이 0.7초로 제한된다.
 *
 * 무늬가 없는 벽이나 단색 이불에서는 실패한다. 그때는 호출자가 자이로로
 * 넘어간다.
 */
class PatchTracker {

    /** 템플릿 (축소본 좌표계) */
    private var template: ByteArray? = null
    private var tw = 0
    private var th = 0

    /** 축소본 좌표계에서의 현재 패치 중심 */
    private var cx = 0f
    private var cy = 0f

    /** 마지막 상관 점수. 진단·신뢰도 판단용. */
    var lastScore = 0f
        private set

    val isActive get() = template != null

    fun clear() {
        template = null
        lastScore = 0f
    }

    /**
     * 검출 결과로 템플릿을 새로 심는다.
     *
     * @param box 회전 보정된 원본 프레임 좌표의 검출 박스
     */
    fun seed(gray: GrayFrame, box: RectF) {
        val s = gray.scale
        val ccx = box.centerX() / s
        val ccy = box.centerY() / s

        // 패치 크기는 박스 크기를 따라가되 상한·하한을 둔다. 너무 작으면
        // 특징이 없고, 너무 크면 배경이 섞여 시차에 다시 휘둘린다.
        val w = (box.width() / s).roundToInt().coerceIn(MIN_PATCH, MAX_PATCH)
        val h = (box.height() / s).roundToInt().coerceIn(MIN_PATCH, MAX_PATCH)

        val x0 = (ccx - w / 2f).roundToInt()
        val y0 = (ccy - h / 2f).roundToInt()
        if (x0 < 0 || y0 < 0 || x0 + w > gray.width || y0 + h > gray.height) {
            clear()
            return
        }

        val t = ByteArray(w * h)
        var i = 0
        for (y in 0 until h) {
            var src = (y0 + y) * gray.width + x0
            for (x in 0 until w) t[i++] = gray.data[src++]
        }
        // 특징이 거의 없는 패치는 추적해도 의미가 없다. 자이로에 맡긴다.
        if (stdDev(t) < MIN_CONTRAST) {
            clear()
            return
        }
        template = t
        tw = w
        th = h
        cx = ccx
        cy = ccy
        lastScore = 1f
    }

    /**
     * 다음 프레임에서 패치를 찾아 이동량을 돌려준다.
     *
     * @return 회전 보정된 원본 프레임 좌표의 (dx, dy). 실패하면 null
     */
    fun track(gray: GrayFrame): Pair<Float, Float>? {
        val t = template ?: return null
        if (tw > gray.width || th > gray.height) return null

        val cxi = (cx - tw / 2f).roundToInt()
        val cyi = (cy - th / 2f).roundToInt()

        var bestScore = -2f
        var bestX = cxi
        var bestY = cyi

        val xFrom = (cxi - SEARCH).coerceAtLeast(0)
        val xTo = (cxi + SEARCH).coerceAtMost(gray.width - tw)
        val yFrom = (cyi - SEARCH).coerceAtLeast(0)
        val yTo = (cyi + SEARCH).coerceAtMost(gray.height - th)
        if (xFrom > xTo || yFrom > yTo) return null

        for (y in yFrom..yTo) {
            for (x in xFrom..xTo) {
                val s = ncc(t, tw, th, gray, x, y)
                if (s > bestScore) {
                    bestScore = s
                    bestX = x
                    bestY = y
                }
            }
        }

        lastScore = bestScore
        if (bestScore < MIN_SCORE) return null

        val ncx = bestX + tw / 2f
        val ncy = bestY + th / 2f
        val dx = (ncx - cx) * gray.scale
        val dy = (ncy - cy) * gray.scale
        cx = ncx
        cy = ncy
        return dx to dy
    }

    /**
     * 평균을 빼고 정규화한 상관. 밝기·대비가 바뀌어도 값이 유지된다.
     * 결과는 -1..1 이고 1 이면 완전히 같다.
     */
    private fun ncc(
        t: ByteArray, w: Int, h: Int, gray: GrayFrame, ox: Int, oy: Int,
    ): Float {
        var sumT = 0
        var sumI = 0
        var i = 0
        for (y in 0 until h) {
            var src = (oy + y) * gray.width + ox
            for (x in 0 until w) {
                sumT += t[i++].toInt() and 0xFF
                sumI += gray.data[src++].toInt() and 0xFF
            }
        }
        val n = w * h
        val mT = sumT.toFloat() / n
        val mI = sumI.toFloat() / n

        var num = 0f
        var dT = 0f
        var dI = 0f
        i = 0
        for (y in 0 until h) {
            var src = (oy + y) * gray.width + ox
            for (x in 0 until w) {
                val a = (t[i++].toInt() and 0xFF) - mT
                val b = (gray.data[src++].toInt() and 0xFF) - mI
                num += a * b
                dT += a * a
                dI += b * b
            }
        }
        val den = sqrt(dT * dI)
        return if (den < 1e-3f) -2f else num / den
    }

    private fun stdDev(t: ByteArray): Float {
        var sum = 0
        for (b in t) sum += b.toInt() and 0xFF
        val m = sum.toFloat() / t.size
        var v = 0f
        for (b in t) {
            val d = (b.toInt() and 0xFF) - m
            v += d * d
        }
        return sqrt(v / t.size)
    }

    companion object {
        /** 축소본 좌표계 기준 패치 변 길이 */
        private const val MIN_PATCH = 12
        private const val MAX_PATCH = 40

        /** 탐색 반경. 30fps 면 프레임 간 이동이 작아 좁아도 충분하다. */
        private const val SEARCH = 10

        /** 이 아래면 추적 실패로 보고 자이로에 맡긴다. */
        private const val MIN_SCORE = 0.45f

        /** 이 아래면 특징이 없는 면(단색 벽·이불)이라 추적하지 않는다. */
        private const val MIN_CONTRAST = 6f
    }
}
