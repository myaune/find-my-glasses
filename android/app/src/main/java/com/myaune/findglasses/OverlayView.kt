package com.myaune.findglasses

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PointF
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin

/**
 * 안경 위치 표시 (기획서 4절).
 *
 * 확대 크롭은 하지 않는다. 사용자는 폰을 들고 실제로 걸어다니며 찾으므로
 * 화면은 위치를 지정하는 역할만 한다.
 *
 * 표시는 하나만 한다. 검출은 한 안경에도 여러 개가 붙지만, "어디지" 를
 * 알려주는 목적에는 여러 개가 오히려 방해가 된다.
 *
 * 화면 밖으로 나가면 가장자리 큰 화살표로 방향을 유지한다. 추론이 0.7~1.9초
 * 걸리므로 이게 없으면 정보가 증발한다.
 */
class OverlayView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : View(context, attrs) {

    private val boxPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val arrowPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
    }
    private val msgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        textAlign = Paint.Align.CENTER
        isFakeBoldText = true
        setShadowLayer(10f, 0f, 2f, Color.BLACK)
    }

    private val path = Path()

    /** 제품 표시 대상. 하나만 그린다. */
    private var target: RectF? = null
    private var confidence = Confidence.LOW
    private var message: String = ""

    /** 그리는 위치만 부드럽게. 추적 좌표는 그대로다. */
    private val smooth = SmoothBox()

    private var srcW = 0
    private var srcH = 0

    fun setFrameSize(w: Int, h: Int) {
        srcW = w
        srcH = h
    }

    fun setTarget(box: RectF?, conf: Confidence, msg: String) {
        target = box
        confidence = conf
        message = msg
        postInvalidateOnAnimation()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (srcW <= 0 || srcH <= 0) return

        // PreviewView 는 기본이 FILL_CENTER 다. 같은 방식으로 맞춘다.
        val scale = maxOf(width.toFloat() / srcW, height.toFloat() / srcH)
        val dx = (width - srcW * scale) / 2f
        val dy = (height - srcH * scale) / 2f
        fun map(r: RectF) = RectF(
            r.left * scale + dx, r.top * scale + dy,
            r.right * scale + dx, r.bottom * scale + dy,
        )

        msgPaint.textSize = width * 0.055f

        val t = target
        if (t == null) {
            smooth.reset()
        } else {
            drawTarget(canvas, smooth.update(map(t), width, System.nanoTime()))
        }

        // 표시할 게 있으면 펄스를 위해 계속 다시 그린다
        if (target != null) postInvalidateOnAnimation()
    }

    private fun drawTarget(canvas: Canvas, box: RectF) {
        // 펄스 — 신뢰도가 높을수록 빠르게
        val phase = (System.currentTimeMillis() % confidence.pulseMs) /
            confidence.pulseMs.toFloat()
        val pulse = 0.5f + 0.5f * sin(phase * 2f * Math.PI).toFloat()

        val onScreen = box.right > 0 && box.left < width && box.bottom > 0 && box.top < height
        if (onScreen) {
            drawOnScreen(canvas, box, pulse)
        } else {
            drawEdgeArrow(canvas, box, pulse)
        }
    }

    private fun drawOnScreen(canvas: Canvas, box: RectF, pulse: Float) {
        val w = width * 0.012f
        boxPaint.color = confidence.color
        boxPaint.strokeWidth = w * (0.75f + 0.5f * pulse)
        boxPaint.alpha = (170 + 85 * pulse).toInt().coerceAtMost(255)

        // 너무 작으면 안경을 못 보는 사용자가 알아볼 수 없다. 최소 크기를 준다.
        val minSide = width * 0.18f
        val r = RectF(box)
        if (r.width() < minSide) {
            val c = r.centerX()
            r.left = c - minSide / 2
            r.right = c + minSide / 2
        }
        if (r.height() < minSide) {
            val c = r.centerY()
            r.top = c - minSide / 2
            r.bottom = c + minSide / 2
        }
        val radius = width * 0.03f
        canvas.drawRoundRect(r, radius, radius, boxPaint)

        // 네모를 가리키는 화살표 네 개. 펄스에 맞춰 안쪽으로 밀려온다.
        arrowPaint.color = confidence.color
        val gap = width * (0.055f - 0.018f * pulse)
        val size = width * 0.05f
        triangle(canvas, r.centerX(), r.top - gap, size, 90f)     // 위 → 아래
        triangle(canvas, r.centerX(), r.bottom + gap, size, 270f) // 아래 → 위
        triangle(canvas, r.left - gap, r.centerY(), size, 0f)     // 왼쪽 → 오른쪽
        triangle(canvas, r.right + gap, r.centerY(), size, 180f)  // 오른쪽 → 왼쪽

        if (message.isNotEmpty()) {
            val y = (r.top - gap - size - width * 0.03f)
                .coerceAtLeast(msgPaint.textSize * 1.4f)
            canvas.drawText(message, width / 2f, y, msgPaint)
        }
    }

    /**
     * 화면 밖에 있을 때 가장자리 큰 화살표로 방향을 유지한다.
     *
     * 추론이 0.7~1.9초라 화면을 벗어나는 순간 정보가 증발하면 쓸 수 없다.
     * 자이로·영상 추적이 위치를 들고 있으므로 방향은 계속 가리킬 수 있다.
     */
    private fun drawEdgeArrow(canvas: Canvas, box: RectF, pulse: Float) {
        val cx = width / 2f
        val cy = height / 2f
        val tx = box.centerX()
        val ty = box.centerY()
        val ang = atan2(ty - cy, tx - cx)

        val margin = width * 0.14f
        val rx = cx - margin
        val ry = cy - margin
        // 화면 테두리 안쪽 타원 위의 점
        val px = cx + rx * cos(ang)
        val py = cy + ry * sin(ang)

        arrowPaint.color = confidence.color
        arrowPaint.alpha = (170 + 85 * pulse).toInt().coerceAtMost(255)
        triangle(canvas, px, py, width * 0.11f * (0.9f + 0.2f * pulse),
            Math.toDegrees(ang.toDouble()).toFloat() + 180f)

        val dist = hypot(tx - cx, ty - cy)
        val msg = if (message.isEmpty()) "" else message
        if (msg.isNotEmpty()) {
            canvas.drawText(msg, cx, cy + msgPaint.textSize * 0.4f, msgPaint)
        }
        // 거리 감각을 주기 위한 작은 점 (멀수록 흐리게)
        boxPaint.color = confidence.color
        boxPaint.strokeWidth = width * 0.006f
        boxPaint.alpha = (60 + 120 * (1f - (dist / (width * 2f)).coerceAtMost(1f))).toInt()
        canvas.drawCircle(cx, cy, width * 0.05f, boxPaint)
    }

    /** headingDeg = 화살표가 가리키는 방향 (0 = 오른쪽, 시계방향) */
    private fun triangle(canvas: Canvas, cx: Float, cy: Float, size: Float, headingDeg: Float) {
        val a = Math.toRadians(headingDeg.toDouble())
        val tip = PointF(cx + (size * cos(a)).toFloat(), cy + (size * sin(a)).toFloat())
        val back = Math.toRadians((headingDeg + 180).toDouble())
        val bx = cx + (size * 0.5f * cos(back)).toFloat()
        val by = cy + (size * 0.5f * sin(back)).toFloat()
        val perp = Math.toRadians((headingDeg + 90).toDouble())
        val ox = (size * 0.55f * cos(perp)).toFloat()
        val oy = (size * 0.55f * sin(perp)).toFloat()

        path.reset()
        path.moveTo(tip.x, tip.y)
        path.lineTo(bx + ox, by + oy)
        path.lineTo(bx - ox, by - oy)
        path.close()
        canvas.drawPath(path, arrowPaint)
    }
}
