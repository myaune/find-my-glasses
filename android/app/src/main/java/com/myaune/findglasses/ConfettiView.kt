package com.myaune.findglasses

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View
import kotlin.math.cos
import kotlin.math.sin
import kotlin.random.Random

/**
 * 찾았을 때 터지는 폭죽.
 *
 * 외부 라이브러리를 쓰지 않는다. 파티클 수백 개를 중력·공기저항·회전으로
 * 떨어뜨리면 충분하다. 세 가지를 섞어 쓴다.
 *   [burstSides]  양옆 아래에서 안쪽 위로 쏘는 대포
 *   [burstCenter] 한 점에서 사방으로 터지는 폭발 (사진 자리)
 *   [sparkle]     중력 없이 제자리에서 반짝이다 사라지는 별
 */
class ConfettiView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : View(context, attrs) {

    private enum class Shape { RECT, CIRCLE, STAR, TWINKLE }

    private class P(
        var x: Float, var y: Float,
        var vx: Float, var vy: Float,
        var rot: Float, val vr: Float,
        val w: Float, val h: Float,
        val color: Int, val shape: Shape,
        /** 남은 수명(초). 끝나기 직전에 흐려진다 */
        var life: Float, val maxLife: Float,
        /** 1 = 보통 중력, 0 = 떠 있음 */
        val gravity: Float,
        val drag: Float,
        /** 반짝이 깜빡임 위상 */
        val phase: Float,
    )

    private val particles = ArrayList<P>()
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val rect = RectF()
    private val star = Path()
    private var lastFrameNs = 0L

    private val colors = intArrayOf(
        Color.rgb(255, 214, 0), Color.rgb(255, 138, 0), Color.rgb(255, 45, 85),
        Color.rgb(168, 199, 250), Color.rgb(140, 230, 140), Color.rgb(200, 140, 255),
        Color.rgb(255, 255, 255),
    )
    private val gold = intArrayOf(
        Color.rgb(255, 236, 140), Color.rgb(255, 214, 0), Color.rgb(255, 255, 255),
    )

    private val scale get() = width / 1080f

    fun clear() {
        particles.clear()
        invalidate()
    }

    /** 양옆 아래쪽에서 화면 중앙 위를 향해 한 번 터뜨린다. */
    fun burstSides() {
        val w = width.toFloat().takeIf { it > 0 } ?: return
        val h = height.toFloat()
        val s = scale

        fun emit(fromLeft: Boolean) {
            val ox = if (fromLeft) -20f * s else w + 20f * s
            val oy = h * 0.72f
            repeat(PER_SIDE) {
                val base = if (fromLeft) -55.0 else -125.0
                val ang = Math.toRadians(base + Random.nextDouble(-22.0, 22.0))
                val speed = (1700f + Random.nextFloat() * 1500f) * s
                particles += confetti(ox, oy, ang, speed, s)
            }
        }
        emit(true)
        emit(false)
        kick()
    }

    /** (cx, cy) 에서 사방으로 폭발. 별이 섞인다. */
    fun burstCenter(cx: Float, cy: Float) {
        if (width == 0) return
        val s = scale
        repeat(CENTER_COUNT) {
            val ang = Random.nextDouble(0.0, Math.PI * 2)
            val speed = (900f + Random.nextFloat() * 1900f) * s
            particles += if (Random.nextInt(5) == 0) {
                P(
                    x = cx, y = cy,
                    vx = (cos(ang) * speed).toFloat(), vy = (sin(ang) * speed).toFloat() - 500f * s,
                    rot = Random.nextFloat() * 360f, vr = Random.nextFloat() * 540f - 270f,
                    w = (26f + Random.nextFloat() * 22f) * s, h = 0f,
                    color = gold[Random.nextInt(gold.size)], shape = Shape.STAR,
                    life = 2.2f, maxLife = 2.2f, gravity = 0.55f, drag = 0.975f, phase = 0f,
                )
            } else {
                confetti(cx, cy, ang, speed, s).also { it.vy -= 500f * s }
            }
        }
        kick()
    }

    /** (cx, cy) 둘레 반경 r 안에서 반짝이는 별 */
    fun sparkle(cx: Float, cy: Float, r: Float, count: Int = SPARKLES) {
        if (width == 0) return
        val s = scale
        repeat(count) {
            val a = Random.nextDouble(0.0, Math.PI * 2)
            val d = r * (0.55f + Random.nextFloat() * 0.6f)
            val life = 0.9f + Random.nextFloat() * 1.3f
            particles += P(
                x = cx + (cos(a) * d).toFloat(), y = cy + (sin(a) * d).toFloat(),
                vx = 0f, vy = -40f * s * Random.nextFloat(),
                rot = 0f, vr = 0f,
                w = (22f + Random.nextFloat() * 30f) * s, h = 0f,
                color = gold[Random.nextInt(gold.size)], shape = Shape.TWINKLE,
                life = life, maxLife = life, gravity = 0f, drag = 1f,
                phase = Random.nextFloat() * 6.28f,
            )
        }
        kick()
    }

    private fun confetti(ox: Float, oy: Float, ang: Double, speed: Float, s: Float) = P(
        x = ox, y = oy,
        vx = (cos(ang) * speed).toFloat(),
        vy = (sin(ang) * speed).toFloat(),
        rot = Random.nextFloat() * 360f,
        vr = Random.nextFloat() * 720f - 360f,
        w = (14f + Random.nextFloat() * 14f) * s,
        h = (8f + Random.nextFloat() * 10f) * s,
        color = colors[Random.nextInt(colors.size)],
        shape = if (Random.nextInt(4) == 0) Shape.CIRCLE else Shape.RECT,
        life = 4f, maxLife = 4f, gravity = 1f, drag = 0.985f, phase = 0f,
    )

    private fun kick() {
        lastFrameNs = 0L
        postInvalidateOnAnimation()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (particles.isEmpty()) return

        val now = System.nanoTime()
        val dt = if (lastFrameNs == 0L) 0.016f else ((now - lastFrameNs) / 1e9f).coerceAtMost(0.05f)
        lastFrameNs = now

        val g = 2600f * scale
        val it = particles.iterator()
        while (it.hasNext()) {
            val p = it.next()
            p.life -= dt
            p.vy += g * p.gravity * dt
            p.vx *= p.drag
            p.vy *= p.drag
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.rot += p.vr * dt
            if (p.life <= 0f || p.y > height + 60f) {
                it.remove()
                continue
            }
            // 마지막 0.4초 동안 흐려진다
            val fade = (p.life / 0.4f).coerceAtMost(1f)
            paint.color = p.color
            paint.alpha = (255 * fade).toInt()

            canvas.save()
            canvas.translate(p.x, p.y)
            canvas.rotate(p.rot)
            when (p.shape) {
                Shape.CIRCLE -> canvas.drawCircle(0f, 0f, p.w * 0.4f, paint)
                Shape.RECT -> {
                    rect.set(-p.w / 2, -p.h / 2, p.w / 2, p.h / 2)
                    canvas.drawRect(rect, paint)
                }
                Shape.STAR -> drawStar(canvas, p.w / 2, 5, 0.45f)
                Shape.TWINKLE -> {
                    // 태어나서 커졌다가 작아지며, 그 사이에 깜빡인다
                    val t = 1f - p.life / p.maxLife
                    val grow = sin(t * Math.PI).toFloat()
                    val blink = 0.65f + 0.35f * sin(p.phase + t * 18f)
                    val r = p.w / 2 * grow * blink
                    if (r > 0.5f) drawStar(canvas, r, 4, 0.22f)
                }
            }
            canvas.restore()
        }
        paint.alpha = 255
        if (particles.isNotEmpty()) postInvalidateOnAnimation()
    }

    /** 뾰족 별. inner = 안쪽 꼭짓점 반지름 비율 */
    private fun drawStar(canvas: Canvas, r: Float, points: Int, inner: Float) {
        star.reset()
        val n = points * 2
        for (i in 0 until n) {
            val a = Math.PI * i / points - Math.PI / 2
            val rr = if (i % 2 == 0) r else r * inner
            val x = (cos(a) * rr).toFloat()
            val y = (sin(a) * rr).toFloat()
            if (i == 0) star.moveTo(x, y) else star.lineTo(x, y)
        }
        star.close()
        canvas.drawPath(star, paint)
    }

    companion object {
        private const val PER_SIDE = 70
        private const val CENTER_COUNT = 110
        private const val SPARKLES = 18
    }
}
