package com.myaune.findglasses

import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.text.method.LinkMovementMethod
import android.text.util.Linkify
import android.util.TypedValue
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

/**
 * 오픈소스 라이선스 화면 (기획서 12·13절 — MVP 필수).
 *
 * 채택한 모델 가중치가 Ultralytics 배포본(yolov8s-worldv2)이라 AGPL-3.0 이다.
 * 기획서는 원본 연구(Tencent AILab YOLO-World) 기준으로 GPL-3.0 이라 적었지만
 * 실제로 앱에 들어가는 파일은 Ultralytics 가 AGPL-3.0 으로 배포한 것이다.
 *
 * AGPL-3.0 은 앱 전체 소스를 공개해야 하므로 이 화면에 소스 코드 위치를 둔다.
 *
 * 라이선스 원문은 res/raw 에 공식 텍스트를 넣었다 (AGPL 은 SPDX, Apache 는
 * apache.org, MIT 는 각 저장소 LICENSE). 기억으로 옮겨 적지 않았다.
 */
class LicensesActivity : AppCompatActivity() {

    private data class Component(
        val name: String,
        val owner: String,
        val license: String,
        val url: String,
        /** 원문이 앱에 들어 있으면 res/raw ID. 독점 약관은 링크만. */
        val textRes: Int?,
        val note: String? = null,
    )

    private val components = listOf(
        Component(
            "YOLO-World v2 (yolov8s-worldv2)", "Ultralytics",
            "AGPL-3.0", "https://github.com/ultralytics/ultralytics",
            R.raw.license_agpl_3_0,
            "Model weights. Original research: Tencent AILab CVC YOLO-World.",
        ),
        Component(
            "CLIP", "OpenAI", "MIT", "https://github.com/openai/CLIP",
            R.raw.license_mit_clip,
            "Text embeddings are computed once at build time and baked into the model.",
        ),
        Component(
            "ONNX Runtime", "Microsoft", "MIT", "https://github.com/microsoft/onnxruntime",
            R.raw.license_mit_onnxruntime,
        ),
        Component(
            "AndroidX (CameraX, AppCompat, Core, Lifecycle, ConstraintLayout, ViewPager2)",
            "The Android Open Source Project", "Apache-2.0",
            "https://developer.android.com/jetpack/androidx", R.raw.license_apache_2_0,
        ),
        Component(
            "Material Components for Android", "Google", "Apache-2.0",
            "https://github.com/material-components/material-components-android",
            R.raw.license_apache_2_0,
        ),
        Component(
            "Kotlin, kotlinx.coroutines", "JetBrains", "Apache-2.0",
            "https://github.com/JetBrains/kotlin", R.raw.license_apache_2_0,
        ),
        Component(
            "Guava", "Google", "Apache-2.0", "https://github.com/google/guava",
            R.raw.license_apache_2_0,
        ),
        Component(
            "Google Mobile Ads SDK, User Messaging Platform", "Google", "Google Mobile Ads SDK Terms",
            "https://developers.google.com/admob/terms", null,
            "Proprietary. Not open source.",
        ),
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = getString(R.string.licenses)

        val pad = dp(20)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, dp(40))
            setBackgroundColor(Color.rgb(18, 18, 18))
        }

        root.addView(text(getString(R.string.licenses), 28f, bold = true, color = Color.WHITE))
        root.addView(text(getString(R.string.licenses_intro), 17f, color = Color.rgb(220, 220, 220))
            .also { it.setPadding(0, dp(10), 0, dp(6)) })

        // 앱 자체의 소스 코드 (AGPL-3.0 의무)
        root.addView(text(getString(R.string.source_code), 20f, bold = true, color = YELLOW)
            .also { it.setPadding(0, dp(18), 0, 0) })
        root.addView(link(SOURCE_URL))
        root.addView(licenseToggle(R.raw.license_agpl_3_0))

        root.addView(divider())

        for (c in components) {
            root.addView(text(c.name, 19f, bold = true, color = Color.WHITE)
                .also { it.setPadding(0, dp(16), 0, 0) })
            root.addView(text("${c.owner} · ${c.license}", 15f, color = YELLOW))
            c.note?.let { root.addView(text(it, 14f, color = Color.rgb(170, 170, 170))) }
            root.addView(link(c.url))
            c.textRes?.let { root.addView(licenseToggle(it)) }
        }

        setContentView(ScrollView(this).apply {
            setBackgroundColor(Color.rgb(18, 18, 18))
            addView(root)
        })
    }

    private fun licenseToggle(res: Int): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val body = text("", 12f, color = Color.rgb(200, 200, 200)).apply {
            typeface = Typeface.MONOSPACE
            visibility = View.GONE
            setPadding(dp(10), dp(8), dp(10), dp(8))
            setBackgroundColor(Color.rgb(32, 32, 32))
        }
        val btn = Button(this).apply {
            text = getString(R.string.view_license)
            isAllCaps = false
            setOnClickListener {
                if (body.visibility == View.GONE) {
                    // 원문이 길어서 펼칠 때만 읽는다
                    if (body.text.isEmpty()) {
                        body.text = resources.openRawResource(res).bufferedReader().use { it.readText() }
                    }
                    body.visibility = View.VISIBLE
                    text = getString(R.string.hide_license)
                } else {
                    body.visibility = View.GONE
                    text = getString(R.string.view_license)
                }
            }
        }
        box.addView(btn)
        box.addView(body)
        return box
    }

    private fun text(s: String, sp: Float, bold: Boolean = false, color: Int) =
        TextView(this).apply {
            text = s
            setTextSize(TypedValue.COMPLEX_UNIT_SP, sp)
            setTextColor(color)
            if (bold) setTypeface(typeface, Typeface.BOLD)
        }

    private fun link(url: String) = text(url, 15f, color = Color.rgb(120, 190, 255)).apply {
        autoLinkMask = Linkify.WEB_URLS
        movementMethod = LinkMovementMethod.getInstance()
        setLinkTextColor(Color.rgb(120, 190, 255))
    }

    private fun divider() = View(this).apply {
        setBackgroundColor(Color.rgb(60, 60, 60))
        layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(1),
        ).also { it.setMargins(0, dp(22), 0, dp(4)) }
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    companion object {
        private val YELLOW = Color.rgb(255, 214, 0)

        /**
         * 앱 소스 코드 위치. AGPL-3.0 의무.
         */
        private const val SOURCE_URL = "https://github.com/myaune/find-my-glasses"
    }
}
