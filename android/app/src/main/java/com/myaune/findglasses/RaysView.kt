package com.myaune.findglasses

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.Shader
import android.util.AttributeSet
import android.view.View
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin

/**
 * 찾았어요 화면에서 사진 뒤로 천천히 도는 햇살 무늬와 은은한 빛.
 *
 * 밝기는 뷰의 alpha 로 조절한다. 중심은 [setCenter] 로 사진 가운데에 맞춘다.
 */
class RaysView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : View(context, attrs) {

    private val rayPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val glowPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val path = Path()

    private var cx = -1f
    private var cy = -1f
    private var angle = 0f
    private var running = false
    private var lastNs = 0L

    fun setCenter(x: Float, y: Float) {
        cx = x
        cy = y
        glowPaint.shader = null
        invalidate()
    }

    fun start() {
        running = true
        lastNs = 0L
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
        val reach = hypot(width.toFloat(), height.toFloat())

        val now = System.nanoTime()
        if (lastNs != 0L) angle += DEG_PER_S * ((now - lastNs) / 1e9f)
        lastNs = now

        // 은은한 빛 — 가운데가 밝고 바깥으로 사라진다
        if (glowPaint.shader == null) {
            glowPaint.shader = RadialGradient(
                x, y, width * 0.75f,
                intArrayOf(Color.argb(150, 255, 236, 160), Color.argb(60, 168, 199, 250), Color.TRANSPARENT),
                floatArrayOf(0f, 0.45f, 1f), Shader.TileMode.CLAMP,
            )
        }
        canvas.drawCircle(x, y, width * 0.75f, glowPaint)

        // 햇살 — 부채꼴 RAYS 개, 하나 걸러 하나
        rayPaint.color = Color.argb(46, 255, 240, 190)
        val step = 360f / RAYS
        for (i in 0 until RAYS step 2) {
            val a0 = Math.toRadians((angle + i * step).toDouble())
            val a1 = Math.toRadians((angle + (i + 1) * step).toDouble())
            path.reset()
            path.moveTo(x, y)
            path.lineTo(x + (cos(a0) * reach).toFloat(), y + (sin(a0) * reach).toFloat())
            path.lineTo(x + (cos(a1) * reach).toFloat(), y + (sin(a1) * reach).toFloat())
            path.close()
            canvas.drawPath(path, rayPaint)
        }

        if (running) postInvalidateOnAnimation()
    }

    companion object {
        private const val RAYS = 24
        private const val DEG_PER_S = 18f
    }
}
