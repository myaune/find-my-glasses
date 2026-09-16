package com.myaune.findglasses

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View
import kotlin.math.sin
import kotlin.random.Random

/**
 * 튜토리얼 그림. 이미지 파일 없이 직접 그린다.
 *
 *   SWEEP     폰이 좌우로 천천히 훑는다
 *   GLASSES   안경 하나 (위에 OverlayView 를 겹쳐 실제 표시를 보여준다)
 *   CONTRAST  대비가 강한 면 vs 복잡한 면
 */
class TutorialArtView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : View(context, attrs) {

    enum class Mode { SWEEP, GLASSES, CONTRAST }

    var mode = Mode.SWEEP
        set(v) { field = v; invalidate() }

    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
    private val path = Path()
    private val rect = RectF()

    /** CONTRAST 의 무늬 — 매 프레임 바뀌면 어지러우니 한 번만 만든다 */
    private val noise = List(90) {
        floatArrayOf(Random.nextFloat(), Random.nextFloat(), Random.nextFloat(), Random.nextFloat())
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        when (mode) {
            Mode.SWEEP -> drawSweep(canvas)
            Mode.GLASSES -> drawGlasses(canvas, width / 2f, height * 0.58f,
                width * 0.26f, Color.rgb(40, 40, 40), Color.rgb(235, 235, 235))
            Mode.CONTRAST -> drawContrast(canvas)
        }
        if (mode == Mode.SWEEP) postInvalidateOnAnimation()
    }

    private fun drawSweep(canvas: Canvas) {
        val w = width.toFloat()
        val h = height.toFloat()

        // 바닥과 안경
        fill.color = Color.rgb(48, 48, 52)
        rect.set(0f, h * 0.72f, w, h)
        canvas.drawRect(rect, fill)
        drawGlasses(canvas, w * 0.66f, h * 0.84f, w * 0.12f,
            Color.rgb(60, 60, 60), Color.rgb(220, 220, 220))

        // 폰이 좌우로 천천히 흔들린다 (4초 주기)
        val t = (System.currentTimeMillis() % 4000L) / 4000f
        val s = sin(t * 2f * Math.PI).toFloat()
        val cx = w / 2f + s * w * 0.22f
        val cy = h * 0.34f
        val pw = w * 0.13f
        val ph = pw * 1.9f

        // 지나간 자리 잔상
        for (i in 1..4) {
            val ts = t - i * 0.025f
            val ss = sin(ts * 2f * Math.PI).toFloat()
            stroke.color = Color.argb(60 - i * 12, 255, 214, 0)
            stroke.strokeWidth = w * 0.008f
            val gx = w / 2f + ss * w * 0.22f
            rect.set(gx - pw / 2, cy - ph / 2, gx + pw / 2, cy + ph / 2)
            canvas.drawRoundRect(rect, pw * 0.18f, pw * 0.18f, stroke)
        }

        // 폰 본체
        fill.color = Color.rgb(250, 250, 250)
        rect.set(cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2)
        canvas.drawRoundRect(rect, pw * 0.18f, pw * 0.18f, fill)
        fill.color = Color.rgb(30, 30, 34)
        rect.inset(pw * 0.08f, pw * 0.1f)
        canvas.drawRoundRect(rect, pw * 0.1f, pw * 0.1f, fill)

        // 카메라가 비추는 영역
        fill.color = Color.argb(46, 255, 214, 0)
        path.reset()
        path.moveTo(cx, cy + ph / 2)
        path.lineTo(cx - w * 0.2f, h * 0.72f)
        path.lineTo(cx + w * 0.2f, h * 0.72f)
        path.close()
        canvas.drawPath(path, fill)

        // 좌우 화살표
        stroke.color = Color.rgb(255, 214, 0)
        stroke.strokeWidth = w * 0.012f
        val ay = h * 0.1f
        canvas.drawLine(w * 0.3f, ay, w * 0.7f, ay, stroke)
        arrowHead(canvas, w * 0.3f, ay, -1f, w * 0.03f)
        arrowHead(canvas, w * 0.7f, ay, 1f, w * 0.03f)
    }

    private fun drawContrast(canvas: Canvas) {
        val w = width.toFloat()
        val h = height.toFloat()
        val gap = w * 0.04f
        val pw = (w - gap * 3) / 2
        val top = h * 0.08f
        val bottom = h * 0.92f

        // 왼쪽 — 단색 면, 안경이 또렷하다
        val l = RectF(gap, top, gap + pw, bottom)
        fill.color = Color.rgb(236, 230, 214)
        canvas.drawRoundRect(l, w * 0.03f, w * 0.03f, fill)
        drawGlasses(canvas, l.centerX(), l.centerY() - h * 0.04f, pw * 0.34f,
            Color.rgb(25, 25, 25), Color.TRANSPARENT)
        badge(canvas, l.centerX(), bottom - h * 0.13f, true)

        // 오른쪽 — 복잡한 무늬, 안경이 묻힌다
        val r = RectF(gap * 2 + pw, top, gap * 2 + pw * 2, bottom)
        canvas.save()
        canvas.clipRect(r)
        fill.color = Color.rgb(120, 100, 150)
        canvas.drawRect(r, fill)
        for (n in noise) {
            fill.color = Color.rgb((80 + n[2] * 150).toInt(), (70 + n[3] * 120).toInt(), 140)
            canvas.drawCircle(r.left + n[0] * r.width(), r.top + n[1] * r.height(),
                w * (0.012f + n[2] * 0.03f), fill)
        }
        drawGlasses(canvas, r.centerX(), r.centerY() - h * 0.04f, pw * 0.34f,
            Color.rgb(110, 90, 140), Color.TRANSPARENT)
        canvas.restore()
        badge(canvas, r.centerX(), bottom - h * 0.13f, false)
    }

    /** ✓ 또는 "가까이" (돋보기 대신 좁혀지는 화살표) */
    private fun badge(canvas: Canvas, cx: Float, cy: Float, ok: Boolean) {
        val rad = width * 0.055f
        fill.color = if (ok) Color.rgb(46, 180, 90) else Color.rgb(255, 138, 0)
        canvas.drawCircle(cx, cy, rad, fill)
        stroke.color = Color.WHITE
        stroke.strokeWidth = rad * 0.22f
        if (ok) {
            path.reset()
            path.moveTo(cx - rad * 0.45f, cy)
            path.lineTo(cx - rad * 0.1f, cy + rad * 0.35f)
            path.lineTo(cx + rad * 0.5f, cy - rad * 0.35f)
            canvas.drawPath(path, stroke)
        } else {
            // → ← 가운데로 모이는 화살표 = 가까이
            canvas.drawLine(cx - rad * 0.6f, cy, cx - rad * 0.15f, cy, stroke)
            canvas.drawLine(cx + rad * 0.6f, cy, cx + rad * 0.15f, cy, stroke)
            arrowHead(canvas, cx - rad * 0.15f, cy, 1f, rad * 0.25f)
            arrowHead(canvas, cx + rad * 0.15f, cy, -1f, rad * 0.25f)
        }
    }

    private fun arrowHead(canvas: Canvas, x: Float, y: Float, dir: Float, size: Float) {
        canvas.drawLine(x, y, x - dir * size, y - size * 0.7f, stroke)
        canvas.drawLine(x, y, x - dir * size, y + size * 0.7f, stroke)
    }

    /** 안경 아이콘. lensW = 한쪽 렌즈 폭 */
    private fun drawGlasses(
        canvas: Canvas, cx: Float, cy: Float, lensW: Float, frame: Int, lens: Int,
    ) {
        val lensH = lensW * 0.72f
        val bridge = lensW * 0.34f
        val sw = lensW * 0.11f

        val left = RectF(cx - bridge / 2 - lensW, cy - lensH / 2, cx - bridge / 2, cy + lensH / 2)
        val right = RectF(cx + bridge / 2, cy - lensH / 2, cx + bridge / 2 + lensW, cy + lensH / 2)

        if (lens != Color.TRANSPARENT) {
            fill.color = Color.argb(70, Color.red(lens), Color.green(lens), Color.blue(lens))
            canvas.drawRoundRect(left, lensW * 0.3f, lensW * 0.3f, fill)
            canvas.drawRoundRect(right, lensW * 0.3f, lensW * 0.3f, fill)
        }
        stroke.color = frame
        stroke.strokeWidth = sw
        canvas.drawRoundRect(left, lensW * 0.3f, lensW * 0.3f, stroke)
        canvas.drawRoundRect(right, lensW * 0.3f, lensW * 0.3f, stroke)

        // 브릿지
        path.reset()
        path.moveTo(left.right, cy - lensH * 0.12f)
        path.quadTo(cx, cy - lensH * 0.38f, right.left, cy - lensH * 0.12f)
        canvas.drawPath(path, stroke)

        // 다리 (접힌 채 살짝 보이게)
        canvas.drawLine(left.left, cy - lensH * 0.25f, left.left - lensW * 0.35f, cy - lensH * 0.05f, stroke)
        canvas.drawLine(right.right, cy - lensH * 0.25f, right.right + lensW * 0.35f, cy - lensH * 0.05f, stroke)
    }
}
