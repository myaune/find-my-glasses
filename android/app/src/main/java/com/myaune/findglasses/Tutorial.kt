package com.myaune.findglasses

import android.graphics.Color
import android.graphics.RectF
import android.graphics.drawable.GradientDrawable
import android.os.Handler
import android.os.Looper
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import androidx.viewpager2.widget.ViewPager2

/**
 * 첫 실행 튜토리얼. 게임 튜토리얼처럼 한 장씩 넘긴다.
 *
 *   1 천천히 둘러보기       — 폰이 좌우로 훑는 그림
 *   2 찾으면 이렇게 표시     — 실제 화면과 같은 OverlayView 로 노랑→연두→초록
 *   3 대비가 강하면 잘 찾음   — 단색 면 ✓ / 복잡한 면은 가까이
 *
 * 스와이프와 버튼 둘 다 된다. 마지막 장의 버튼이 "시작하기" 로 바뀐다.
 * 안경을 안 쓴 사용자가 읽는다는 전제로 글씨를 크게 쓴다 (기획서 4절).
 */
class Tutorial(
    private val pager: ViewPager2,
    private val dots: LinearLayout,
    private val next: Button,
    skip: TextView,
    private val onFinish: () -> Unit,
) {
    private data class Page(val art: TutorialArtView.Mode, val titleRes: Int, val bodyRes: Int)

    private val pages = listOf(
        Page(TutorialArtView.Mode.SWEEP, R.string.tut_step1_title, R.string.tut_step1_body),
        Page(TutorialArtView.Mode.GLASSES, R.string.tut_step2_title, R.string.tut_step2_body),
        Page(TutorialArtView.Mode.CONTRAST, R.string.tut_step3_title, R.string.tut_step3_body),
    )

    private val ctx = pager.context
    private val handler = Handler(Looper.getMainLooper())
    private var demo: OverlayView? = null
    private var demoStep = 0
    private var running = false

    init {
        pager.adapter = Adapter()
        pager.registerOnPageChangeCallback(object : ViewPager2.OnPageChangeCallback() {
            override fun onPageSelected(position: Int) = render(position)
        })
        next.setOnClickListener {
            val i = pager.currentItem
            if (i < pages.size - 1) pager.currentItem = i + 1 else onFinish()
        }
        skip.setOnClickListener { onFinish() }
        buildDots()
    }

    fun start() {
        pager.setCurrentItem(0, false)
        render(0)
        running = true
        demoStep = 0
        tick()
    }

    fun stop() {
        running = false
        handler.removeCallbacksAndMessages(null)
        demo?.setTarget(null, Confidence.LOW, "")
    }

    private fun render(position: Int) {
        for (i in 0 until dots.childCount) {
            dots.getChildAt(i).background = dot(i == position)
        }
        next.setText(if (position == pages.size - 1) R.string.tut_start else R.string.tut_next)
    }

    /** 2장 그림: 신뢰도가 올라가며 색이 바뀌는 것을 순서대로 보여준다 */
    private fun tick() {
        if (!running) return
        demo?.let { d ->
            val w = d.width
            val h = d.height
            if (w > 0 && h > 0) {
                d.setFrameSize(w, h)
                val conf = Confidence.values()[demoStep % Confidence.values().size]
                // TutorialArtView 가 안경을 그리는 자리와 맞춘다
                val bw = w * 0.66f
                val bh = w * 0.26f
                val cy = h * 0.58f
                d.setTarget(
                    RectF(w / 2f - bw / 2, cy - bh / 2, w / 2f + bw / 2, cy + bh / 2),
                    conf, ctx.getString(conf.messageRes),
                )
                demoStep++
            }
        }
        handler.postDelayed({ tick() }, 1500)
    }

    private fun buildDots() {
        dots.removeAllViews()
        repeat(pages.size) {
            dots.addView(View(ctx).apply {
                layoutParams = LinearLayout.LayoutParams(dp(10), dp(10)).also {
                    it.setMargins(dp(6), 0, dp(6), 0)
                }
            })
        }
        render(0)
    }

    private fun dot(active: Boolean) = GradientDrawable().apply {
        shape = GradientDrawable.OVAL
        setColor(if (active) Color.rgb(255, 214, 0) else Color.rgb(90, 90, 90))
    }

    private fun dp(v: Int) = (v * ctx.resources.displayMetrics.density).toInt()

    private inner class Adapter : RecyclerView.Adapter<Adapter.Holder>() {
        inner class Holder(val root: LinearLayout) : RecyclerView.ViewHolder(root)

        override fun getItemCount() = pages.size

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
            val root = LinearLayout(ctx).apply {
                orientation = LinearLayout.VERTICAL
                layoutParams = ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT,
                )
                setPadding(dp(28), dp(4), dp(28), dp(4))
                gravity = Gravity.CENTER_HORIZONTAL
            }
            return Holder(root)
        }

        override fun onBindViewHolder(holder: Holder, position: Int) {
            val p = pages[position]
            val root = holder.root
            root.removeAllViews()

            val frame = FrameLayout(ctx).apply {
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f,
                ).also { it.bottomMargin = dp(20) }
                background = GradientDrawable().apply {
                    cornerRadius = dp(20).toFloat()
                    setColor(Color.rgb(34, 34, 38))
                }
                clipToOutline = true
            }
            frame.addView(TutorialArtView(ctx).apply { mode = p.art })

            if (p.art == TutorialArtView.Mode.GLASSES) {
                // 실제 화면과 같은 코드로 표시를 그린다
                val ov = OverlayView(ctx)
                frame.addView(ov)
                demo = ov
            }
            root.addView(frame)

            root.addView(TextView(ctx).apply {
                setText(p.titleRes)
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 30f)
                setTypeface(typeface, android.graphics.Typeface.BOLD)
                setTextColor(Color.rgb(255, 214, 0))
                gravity = Gravity.CENTER
            })
            root.addView(TextView(ctx).apply {
                setText(p.bodyRes)
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f)
                setTextColor(Color.rgb(230, 230, 230))
                setLineSpacing(0f, 1.25f)
                gravity = Gravity.CENTER
                setPadding(0, dp(12), 0, dp(8))
            })
        }
    }
}
