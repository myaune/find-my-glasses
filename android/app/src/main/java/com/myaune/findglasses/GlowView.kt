package com.myaune.findglasses

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RadialGradient
import android.graphics.Shader
import android.util.AttributeSet
import android.view.View
import kotlin.math.sin

/**
 * 찾았어요 화면에서 사진 뒤로 은은하게 숨쉬는 빛.
 *
 * 방사형 줄무늬(햇살)는 쓰지 않는다. 욱일기를 떠올리게 한다.
 * 둥근 빛 하나가 천천히 커졌다 작아지며 색이 노랑 → 분홍 → 연파랑으로 돈다.
 */
class GlowView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : View(context, attrs) {

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private var cx = -1f
    private var cy = -1f
    private var running = false
    private var startNs = 0L

    private val hues = intArrayOf(
        Color.rgb(255, 226, 130), Color.rgb(255, 150, 190), Color.rgb(168, 199, 250),
    )

    fun setCenter(x: Float, y: Float) {
        cx = x
        cy = y
        invalidate()
    }

    fun start() {
        running = true
        startNs = System.nanoTime()
        postInvalidateOnAnimation()
    }

    fun stop() {
        running = false
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (width == 0) return
        val x = if (cx < 0) width / 2f else cx
        val y = if (cy < 0) height / 2f else cy
        val t = (System.nanoTime() - startNs) / 1e9f

        // 숨쉬기 — 0.9초 주기로 크기가 ±8%
        val r = width * 0.72f * (1f + 0.08f * sin(t * 7f))
        // 색이 천천히 돈다 (1.8초에 한 바퀴)
        val f = (t / 0.6f) % hues.size
        val i = f.toInt()
        val c = blend(hues[i], hues[(i + 1) % hues.size], f - i)

        paint.shader = RadialGradient(
            x, y, r,
            intArrayOf(
                Color.argb(170, Color.red(c), Color.green(c), Color.blue(c)),
                Color.argb(55, Color.red(c), Color.green(c), Color.blue(c)),
                Color.TRANSPARENT,
            ),
            floatArrayOf(0f, 0.5f, 1f), Shader.TileMode.CLAMP,
        )
        canvas.drawCircle(x, y, r, paint)
        if (running) postInvalidateOnAnimation()
    }

    private fun blend(a: Int, b: Int, k: Float) = Color.rgb(
        (Color.red(a) + (Color.red(b) - Color.red(a)) * k).toInt(),
        (Color.green(a) + (Color.green(b) - Color.green(a)) * k).toInt(),
        (Color.blue(a) + (Color.blue(b) - Color.blue(a)) * k).toInt(),
    )
}
