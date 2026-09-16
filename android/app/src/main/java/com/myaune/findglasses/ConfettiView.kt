package com.myaune.findglasses

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View
import kotlin.math.cos
import kotlin.math.sin
import kotlin.random.Random

/**
 * 찾았을 때 양옆에서 터지는 폭죽.
 *
 * 외부 라이브러리를 쓰지 않는다. 파티클 수십 개를 중력·공기저항·회전으로
 * 떨어뜨리면 충분하다.
 */
class ConfettiView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : View(context, attrs) {

    private class P(
        var x: Float, var y: Float,
        var vx: Float, var vy: Float,
        var rot: Float, val vr: Float,
        val w: Float, val h: Float,
        val color: Int, val circle: Boolean,
    )

    private val particles = ArrayList<P>()
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val rect = RectF()
    private var lastFrameNs = 0L

    private val colors = intArrayOf(
        Color.rgb(255, 214, 0), Color.rgb(255, 138, 0), Color.rgb(255, 45, 85),
        Color.rgb(120, 200, 255), Color.rgb(140, 230, 140), Color.rgb(200, 140, 255),
    )

    /** 양옆 아래쪽에서 화면 중앙 위를 향해 한 번 터뜨린다. */
    fun burst() {
        particles.clear()
        val w = width.toFloat().takeIf { it > 0 } ?: return
        val h = height.toFloat()
        val scale = w / 1080f

        fun emit(fromLeft: Boolean) {
            val ox = if (fromLeft) -20f * scale else w + 20f * scale
            val oy = h * 0.72f
            repeat(PER_SIDE) {
                // 안쪽 위를 향해 부채꼴로
                val base = if (fromLeft) -55.0 else -125.0
                val ang = Math.toRadians(base + Random.nextDouble(-22.0, 22.0))
                val speed = (1700f + Random.nextFloat() * 1500f) * scale
                particles += P(
                    x = ox, y = oy,
                    vx = (cos(ang) * speed).toFloat(),
                    vy = (sin(ang) * speed).toFloat(),
                    rot = Random.nextFloat() * 360f,
                    vr = Random.nextFloat() * 720f - 360f,
                    w = (14f + Random.nextFloat() * 14f) * scale,
                    h = (8f + Random.nextFloat() * 10f) * scale,
                    color = colors[Random.nextInt(colors.size)],
                    circle = Random.nextInt(4) == 0,
                )
            }
        }
        emit(true)
        emit(false)
        lastFrameNs = 0L
        postInvalidateOnAnimation()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (particles.isEmpty()) return

        val now = System.nanoTime()
        val dt = if (lastFrameNs == 0L) 0.016f else ((now - lastFrameNs) / 1e9f).coerceAtMost(0.05f)
        lastFrameNs = now

        val g = 2600f * (width / 1080f)
        val it = particles.iterator()
        while (it.hasNext()) {
            val p = it.next()
            p.vy += g * dt
            p.vx *= 0.985f          // 공기저항
            p.vy *= 0.985f
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.rot += p.vr * dt
            if (p.y > height + 60f) {
                it.remove()
                continue
            }
            paint.color = p.color
            canvas.save()
            canvas.translate(p.x, p.y)
            canvas.rotate(p.rot)
            if (p.circle) {
                canvas.drawCircle(0f, 0f, p.w * 0.4f, paint)
            } else {
                rect.set(-p.w / 2, -p.h / 2, p.w / 2, p.h / 2)
                canvas.drawRect(rect, paint)
            }
            canvas.restore()
        }
        if (particles.isNotEmpty()) postInvalidateOnAnimation()
    }

    companion object {
        private const val PER_SIDE = 70
    }
}
