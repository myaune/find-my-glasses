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
import kotlin.math.hypot
import kotlin.math.sin
import kotlin.random.Random

/**
 * 찾았을 때 터지는 폭죽.
 *
 * 외부 라이브러리를 쓰지 않는다. 파티클 수백 개를 중력·공기저항·회전으로
 * 떨어뜨리면 충분하다. 몇 가지를 섞어 쓴다.
 *   [burstSides]  양옆 아래에서 안쪽 위로 쏘는 대포
 *   [burstCenter] 한 점에서 사방으로 터지는 폭발 (사진 자리)
 *   [sparkle]     중력 없이 제자리에서 반짝이다 사라지는 별
 *   [ring]        둥글게 퍼지는 충격파
 *   [firework]    아래에서 쏘아 올려 꼬리를 끌며 터지는 불꽃
 *   [rain]        위에서 쏟아지는 색종이
 */
class ConfettiView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : View(context, attrs) {

    private enum class Shape { RECT, CIRCLE, STAR, TWINKLE, RING, ROCKET, SPARK }

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
        val phase: Float = 0f,
    )

    /** 불꽃이 터질 때 알린다 (진동용) */
    var onPop: (() -> Unit)? = null

    private val particles = ArrayList<P>()
    private val born = ArrayList<P>()
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val rect = RectF()
    private val star = Path()
    private var lastFrameNs = 0L
    private var rainUntilNs = 0L
    private var rainCarry = 0f

    private val colors = intArrayOf(
        Color.rgb(255, 214, 0), Color.rgb(255, 138, 0), Color.rgb(255, 45, 85),
        Color.rgb(168, 199, 250), Color.rgb(140, 230, 140), Color.rgb(200, 140, 255),
        Color.rgb(255, 255, 255),
    )
    private val gold = intArrayOf(
        Color.rgb(255, 236, 140), Color.rgb(255, 214, 0), Color.rgb(255, 255, 255),
    )
    /** 불꽃 한 발은 한두 색으로 터져야 예쁘다 */
    private val fireworkSets = arrayOf(
        intArrayOf(Color.rgb(255, 80, 120), Color.rgb(255, 200, 220)),
        intArrayOf(Color.rgb(120, 200, 255), Color.rgb(230, 245, 255)),
        intArrayOf(Color.rgb(255, 214, 0), Color.rgb(255, 250, 200)),
        intArrayOf(Color.rgb(150, 240, 150), Color.rgb(230, 255, 230)),
        intArrayOf(Color.rgb(200, 140, 255), Color.rgb(245, 230, 255)),
    )

    private val scale get() = width / 1080f

    fun clear() {
        particles.clear()
        rainUntilNs = 0L
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
                    life = 2.2f, maxLife = 2.2f, gravity = 0.55f, drag = 0.975f,
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

    /** 둥글게 퍼지는 충격파. 반지름이 화면 폭의 [reach] 배까지 커지며 옅어진다. */
    fun ring(cx: Float, cy: Float, color: Int = Color.WHITE, reach: Float = 0.85f) {
        if (width == 0) return
        particles += P(
            x = cx, y = cy, vx = 0f, vy = 0f, rot = 0f, vr = 0f,
            w = width * reach, h = 26f * scale,
            color = color, shape = Shape.RING,
            life = RING_S, maxLife = RING_S, gravity = 0f, drag = 1f,
        )
        kick()
    }

    /** 화면 아래 x 에서 쏘아 올려 높이 toY 근처에서 터진다. */
    fun firework(x: Float, toY: Float) {
        if (width == 0) return
        val s = scale
        val fromY = height + 20f * s
        // 등가속도: 멈추는 높이가 toY 가 되도록 초속을 정한다
        val g = GRAVITY * s * ROCKET_G
        val v = kotlin.math.sqrt(2f * g * (fromY - toY))
        val t = v / g
        particles += P(
            x = x, y = fromY, vx = Random.nextFloat() * 120f * s - 60f * s, vy = -v,
            rot = 0f, vr = 0f, w = 12f * s, h = 0f,
            color = Color.rgb(255, 240, 200), shape = Shape.ROCKET,
            life = t, maxLife = t, gravity = ROCKET_G, drag = 1f,
        )
        kick()
    }

    /** 앞으로 [ms] 동안 위에서 색종이가 쏟아진다 */
    fun rain(ms: Long) {
        rainUntilNs = System.nanoTime() + ms * 1_000_000
        kick()
    }

    private fun explode(x: Float, y: Float) {
        val s = scale
        val set = fireworkSets[Random.nextInt(fireworkSets.size)]
        val n = FIREWORK_SPARKS
        for (i in 0 until n) {
            // 고르게 둥근 모양이 되게 각도를 나눈다. 속도는 조금씩 다르게
            val a = Math.PI * 2 * i / n + Random.nextDouble(-0.05, 0.05)
            val sp = (900f + Random.nextFloat() * 350f) * s
            val life = 1.1f + Random.nextFloat() * 0.5f
            born += P(
                x = x, y = y, vx = (cos(a) * sp).toFloat(), vy = (sin(a) * sp).toFloat(),
                rot = 0f, vr = 0f, w = (7f + Random.nextFloat() * 5f) * s, h = 0f,
                color = set[if (i % 3 == 0) 1 else 0], shape = Shape.SPARK,
                life = life, maxLife = life, gravity = 0.32f, drag = 0.955f,
            )
        }
        born += P(
            x = x, y = y, vx = 0f, vy = 0f, rot = 0f, vr = 0f,
            w = width * 0.32f, h = 14f * s, color = set[0], shape = Shape.RING,
            life = 0.45f, maxLife = 0.45f, gravity = 0f, drag = 1f,
        )
        onPop?.invoke()
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
        life = 4f, maxLife = 4f, gravity = 1f, drag = 0.985f,
    )

    private fun kick() {
        lastFrameNs = 0L
        postInvalidateOnAnimation()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val now = System.nanoTime()
        val raining = now < rainUntilNs
        if (particles.isEmpty() && !raining) return

        val dt = if (lastFrameNs == 0L) 0.016f else ((now - lastFrameNs) / 1e9f).coerceAtMost(0.05f)
        lastFrameNs = now
        val s = scale

        // 색종이 비 — 위에서 천천히 흔들리며 떨어진다
        if (raining) {
            rainCarry += RAIN_PER_S * dt
            while (rainCarry >= 1f) {
                rainCarry -= 1f
                particles += confetti(
                    Random.nextFloat() * width, -30f * s, Math.PI / 2,
                    (150f + Random.nextFloat() * 250f) * s, s,
                ).also { it.vx = Random.nextFloat() * 300f * s - 150f * s }
            }
        }

        val g = GRAVITY * s
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
                if (p.shape == Shape.ROCKET) explode(p.x, p.y)
                it.remove()
                continue
            }
            val fade = (p.life / 0.4f).coerceAtMost(1f)

            when (p.shape) {
                Shape.RING -> {
                    // 빠르게 퍼지다 느려진다 (ease-out), 굵기는 가늘어진다
                    val t = 1f - p.life / p.maxLife
                    val e = 1f - (1f - t) * (1f - t) * (1f - t)
                    stroke.color = p.color
                    stroke.alpha = (220 * (1f - t)).toInt()
                    stroke.strokeWidth = p.h * (1f - t) + 1f
                    canvas.drawCircle(p.x, p.y, p.w * e, stroke)
                    continue
                }
                Shape.ROCKET, Shape.SPARK -> {
                    // 움직인 방향으로 꼬리를 끈다
                    val trail = if (p.shape == Shape.ROCKET) 0.06f else 0.035f
                    stroke.color = p.color
                    stroke.alpha = (255 * fade).toInt()
                    stroke.strokeWidth = p.w
                    val tx = p.x - p.vx * trail
                    val ty = p.y - p.vy * trail
                    if (hypot(p.x - tx, p.y - ty) < 1f) canvas.drawPoint(p.x, p.y, stroke)
                    else canvas.drawLine(tx, ty, p.x, p.y, stroke)
                    if (p.shape == Shape.ROCKET) {
                        paint.color = Color.WHITE
                        paint.alpha = 255
                        canvas.drawCircle(p.x, p.y, p.w * 0.7f, paint)
                    }
                    continue
                }
                else -> Unit
            }

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
                else -> Unit
            }
            canvas.restore()
        }
        if (born.isNotEmpty()) {
            particles += born
            born.clear()
        }
        paint.alpha = 255
        if (particles.isNotEmpty() || raining) postInvalidateOnAnimation()
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
        private const val FIREWORK_SPARKS = 56
        private const val RAIN_PER_S = 60f
        private const val RING_S = 0.7f
        private const val GRAVITY = 2600f
        /** 불꽃 로켓은 중력을 덜 받게 해서 느긋하게 올라간다 */
        private const val ROCKET_G = 0.45f
    }
}
