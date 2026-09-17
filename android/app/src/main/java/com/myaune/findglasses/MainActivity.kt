package com.myaune.findglasses

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.RectF
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Bundle
import android.os.Looper
import android.util.Log
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.myaune.findglasses.databinding.DialogSettingsBinding
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import com.myaune.findglasses.databinding.ActivityMainBinding
import java.io.File
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * 안경 찾기 (기획서 4절).
 *
 * 구조는 기획서 8절대로 detector 와 제품 UI 를 분리한다. 모델을 교체해도
 * 화면 코드는 유지된다.
 *
 *   CameraX ─ 최신 프레임
 *     ├─ 추론이 노는 중이면 → 별도 스레드로 추론 (0.7~1.9초)
 *     └─ 추론이 도는 중이면 → 그 프레임으로 패치 추적 (이동 보정)
 *   Tracker ─ 자이로 + 영상 추적으로 위치 유지, temporal filter
 *   OverlayView ─ 네모 하나 + 화살표, 화면 밖이면 가장자리 화살표
 *   Feedback ─ 음성 + 진동
 *
 * 추론이 느린 것을 전제로 설계한다. SD685 에서 0.5~1.5 FPS 다. 그래서
 * 프레임 사이를 추적으로 메우는 것이 이 앱의 핵심이고, 화면 표시는 추론
 * 주기와 무관하게 부드럽게 움직인다.
 *
 * 측정용 개발자 도구는 출시 전에 걷어냈다. 재측정이 필요하면 git 기록(2026-09-13 이전)에 있다.
 */
class MainActivity : AppCompatActivity(), SensorEventListener {

    private lateinit var binding: ActivityMainBinding
    private lateinit var analysisExecutor: ExecutorService
    private lateinit var inferExecutor: ExecutorService
    private lateinit var feedback: Feedback
    private lateinit var ads: Ads
    private lateinit var purchases: Purchases
    private lateinit var consent: Consent
    private var adsStarted = false

    private var detector: Detector? = null
    private val tracker = Tracker()
    private val patch = PatchTracker()
    private val gray = GrayFrame()
    private val sweep = SweepGuide()
    private val busy = AtomicBoolean(false)

    private val selectedModel = ModelCatalog.MODELS.first()
    /** 입력 해상도. 사용자 화질 선택이 바꾸고 다음 실행에도 기억한다. */
    private var selectedSize = ModelCatalog.QUALITIES.first().size

    // 자이로: ROTATION_VECTOR → device→world 회전행렬.
    // 배열을 제자리에서 고치지 않고 매번 새로 만들어 갈아끼운다. 촬영 시점
    // 스냅샷이 일관돼야 한다.
    @Volatile
    private var latestR: FloatArray? = null

    private var focalMm = 0f
    private var sensorWidthMm = 0f

    private var fps = 0f
    private var tooFast = false

    // 추론이 끝나면 추적 템플릿을 다시 심어야 한다. 그런데 gray 는 분석
    // 스레드가 매 프레임 덮어쓰므로 추론 스레드에서 건드리면 경합이다.
    // 플래그만 세우고 실제 seed 는 gray 를 소유한 분석 스레드에서 한다.
    @Volatile
    private var needsReseed = false

    /** 찾았다 이후 축하 화면·광고가 끝날 때까지. 추론과 안내를 멈춘다. */
    @Volatile
    private var celebrating = false

    /** 튜토리얼이 떠 있는 동안. 안내를 멈춘다. */
    @Volatile
    private var tutorialOpen = false

    /** 찾을 대상. 저장하지 않는다 — 앱을 켜면 항상 안경이다. */
    private var target = ModelCatalog.Target.GLASSES
    private lateinit var tutorial: Tutorial

    /**
     * 세션 최고점 검출의 사진. 찾았을 때 가운데 띄운다.
     * 추론 스레드가 쓰고 UI 스레드가 읽는다.
     */
    @Volatile
    private var snapshot: android.graphics.Bitmap? = null
    @Volatile
    private var snapshotScore = 0f

    private val uiHandler = android.os.Handler(Looper.getMainLooper())

    private val requestCamera = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startCamera() else Log.w(TAG, "카메라 권한 거부")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        analysisExecutor = Executors.newSingleThreadExecutor()
        inferExecutor = Executors.newSingleThreadExecutor()
        feedback = Feedback(this)
        purchases = GooglePlayPurchases(this)
        ads = Ads(this)
        // 마지막으로 확인한 구매 상태로 먼저 정하고, 스토어 확인 결과로 다시 맞춘다
        ads.enabled = !purchases.adFree
        purchases.start { adFree ->
            if (adFree) ads.disable(binding.bottomBar)
        }
        consent = Consent(this)
        // 광고는 동의 확인이 끝난 뒤에만 초기화한다 (유럽 등)
        if (ads.enabled) consent.gather { runOnUiThread { startAds() } }

        binding.btnFound.setOnClickListener { onFound() }

        feedback.voiceEnabled = prefs().getBoolean(PREF_VOICE, true)
        feedback.vibrationEnabled = prefs().getBoolean(PREF_VIBRATION, true)
        binding.settingsButton.setOnClickListener { showSettings() }
        binding.targetButton.setOnClickListener { showTargetPicker() }
        renderTargetButton()

        binding.helpButton.setOnClickListener { showTutorial() }
        tutorial = Tutorial(binding.tutPager, binding.tutDots, binding.tutStart, binding.tutSkip) {
            closeTutorial()
        }
        binding.tutLicenses.setOnClickListener {
            startActivity(Intent(this, LicensesActivity::class.java))
        }
        setupQuality()

        // 모델 로딩은 튜토리얼과 무관하게 바로 시작한다. 수십 초 걸릴 수 있어
        // 사용자가 튜토리얼을 읽는 동안 끝나 있는 게 낫다.
        loadDetectorAsync()

        if (!prefs().getBoolean(PREF_TUTORIAL_SEEN, false)) {
            showTutorial()
        } else {
            requestCameraIfNeeded()
        }
    }

    private fun startAds() {
        if (adsStarted || !ads.enabled) return
        adsStarted = true
        ads.init()
        ads.attachBanner(binding.bottomBar)
        ads.preloadInterstitial()
    }

    private fun resetSession() {
        tracker.reset()
        patch.clear()
        sweep.reset()
        feedback.reset()
        snapshotScore = 0f
        snapshot = null
        runOnUiThread {
            binding.btnFound.visibility = View.GONE
            binding.overlay.setTarget(null, Confidence.LOW, "")
        }
    }

    private fun prefs() = getSharedPreferences("app", MODE_PRIVATE)

    private fun requestCameraIfNeeded() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            != PackageManager.PERMISSION_GRANTED
        ) requestCamera.launch(Manifest.permission.CAMERA)
        else if (detector != null) startCamera()
    }

    // ── 다른 물건 찾기 (부가 기능) ──────────────────────────────────────────
    /**
     * 우측 하단 구석의 작은 버튼. 안경 외 대상은 테스트하지 않은 부가 기능이라
     * 고르는 창에 그렇게 적는다. 모델은 그대로 두고 대상 클래스만 바꾼다.
     */
    private fun showTargetPicker() {
        val all = ModelCatalog.Target.values()
        val names = all.map { "${it.emoji}  ${getString(it.labelRes)}" }.toTypedArray()
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.target_title)
            .setSingleChoiceItems(names, all.indexOf(target)) { dialog, which ->
                dialog.dismiss()
                setTarget(all[which])
            }
            .setNegativeButton(android.R.string.cancel, null)
            .also { b ->
                // 제목 아래 경고. setMessage 는 목록과 함께 못 쓰므로 커스텀 제목 영역을 쓴다.
                b.setCustomTitle(layoutInflater.inflate(R.layout.dialog_target_title, null))
            }
            .show()
    }

    private fun setTarget(t: ModelCatalog.Target) {
        if (t == target) return
        target = t
        detector?.targetClasses = t.classes
        resetSession()
        renderTargetButton()
    }

    /** 안경일 때는 눈에 안 띄게, 다른 물건일 때는 지금 무엇을 찾는지 보이게 */
    private fun renderTargetButton() {
        val b = binding.targetButton
        if (target == ModelCatalog.Target.GLASSES) {
            b.text = getString(R.string.target_other)
            b.alpha = 0.55f
        } else {
            b.text = "${target.emoji} ${getString(target.labelRes)}"
            b.alpha = 1f
        }
    }

    // ── 설정 ────────────────────────────────────────────────────────────────
    /**
     * 음성 / 진동 켜고 끄기, 앱 언어.
     *
     * 언어는 AppCompat 앱별 언어로 바꾼다. 화면이 다시 만들어지므로 대화상자를
     * 닫을 때 한 번만 적용한다. Android 13+ 에서는 시스템 설정의 앱 언어와 같은 값이다.
     */
    private fun showSettings() {
        val v = DialogSettingsBinding.inflate(layoutInflater)
        v.swVoice.isChecked = feedback.voiceEnabled
        v.swVibration.isChecked = feedback.vibrationEnabled
        v.swVoice.setOnCheckedChangeListener { _, on ->
            feedback.voiceEnabled = on
            prefs().edit().putBoolean(PREF_VOICE, on).apply()
        }
        v.swVibration.setOnCheckedChangeListener { _, on ->
            feedback.vibrationEnabled = on
            prefs().edit().putBoolean(PREF_VIBRATION, on).apply()
        }

        // "폰 설정 따르기" 대신 지금 실제로 쓰는 언어 이름을 보여준다.
        // 앱에서 따로 고른 적이 없으면 폰 언어, 목록에 없는 언어면 영어(기본 문자열).
        v.spLanguage.adapter = android.widget.ArrayAdapter(
            this, R.layout.spinner_item_pill, LANGUAGES.map { it.second }
        ).also { it.setDropDownViewResource(R.layout.spinner_dropdown_item) }
        val appLocale = AppCompatDelegate.getApplicationLocales()[0]
        val shown = appLocale ?: android.content.res.Resources.getSystem().configuration.locales[0]
        val currentIndex = languageIndex(shown).takeIf { it >= 0 }
            ?: LANGUAGES.indexOfFirst { it.first == "en" }
        v.spLanguage.setSelection(currentIndex)

        bindSupportCard(v)

        v.btnPrivacyPolicy.setOnClickListener {
            startActivity(Intent(Intent.ACTION_VIEW, android.net.Uri.parse(PRIVACY_POLICY_URL)))
        }
        v.btnPrivacyOptions.visibility = if (consent.privacyOptionsRequired) View.VISIBLE else View.GONE
        v.btnPrivacyOptions.setOnClickListener { consent.showPrivacyOptions() }

        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.settings)
            .setView(v.root)
            .setPositiveButton(R.string.settings_done) { _, _ ->
                val pick = v.spLanguage.selectedItemPosition
                if (pick != currentIndex) {
                    AppCompatDelegate.setApplicationLocales(
                        LocaleListCompat.forLanguageTags(LANGUAGES[pick].first)
                    )
                }
            }
            .show()
    }

    /**
     * 응원 카드 (광고 제거 IAP). 결제 자체는 [Purchases] 구현이 맡는다.
     * 이미 샀으면 버튼 대신 고맙다는 말만 남긴다.
     */
    private fun bindSupportCard(v: DialogSettingsBinding) {
        fun showBought() {
            v.supportTitle.setText(R.string.support_thanks_title)
            v.supportBody.setText(R.string.support_thanks_body)
            v.btnSupport.visibility = View.GONE
            v.btnRestore.visibility = View.GONE
        }
        if (purchases.adFree || !ads.enabled) { showBought(); return }

        purchases.removeAdsPrice { price ->
            runOnUiThread {
                v.btnSupport.text = if (price == null) getString(R.string.support_buy_noprice)
                else getString(R.string.support_buy, price)
            }
        }

        val onResult = { r: Purchases.Result ->
            runOnUiThread {
                when (r) {
                    Purchases.Result.PURCHASED, Purchases.Result.RESTORED -> {
                        ads.disable(binding.bottomBar)
                        showBought()
                        toast(R.string.support_thanks_title)
                    }
                    Purchases.Result.NOTHING_TO_RESTORE -> toast(R.string.purchases_nothing)
                    Purchases.Result.UNAVAILABLE -> toast(R.string.purchases_unavailable)
                    Purchases.Result.CANCELLED -> Unit
                }
            }
        }
        v.btnSupport.setOnClickListener { purchases.buyRemoveAds(this, onResult) }
        v.btnRestore.setOnClickListener { purchases.restore(onResult) }
    }

    /** 로케일 → LANGUAGES 위치. 중국어는 번체 지역·문자면 zh-TW, 아니면 zh-CN. */
    private fun languageIndex(l: java.util.Locale): Int {
        val tag = when (val lang = l.language) {
            "in" -> "id"   // 자바 옛 인도네시아어 코드
            "zh" -> if (l.script == "Hant" || l.country in setOf("TW", "HK", "MO")) "zh-TW" else "zh-CN"
            else -> lang
        }
        return LANGUAGES.indexOfFirst { it.first == tag }
    }

    private fun toast(res: Int) =
        android.widget.Toast.makeText(this, res, android.widget.Toast.LENGTH_SHORT).show()

    // ── 튜토리얼 ────────────────────────────────────────────────────────────
    /** 첫 실행에 한 번 띄운다. 우측 상단 ? 로 다시 볼 수 있다. 한 장씩 넘긴다. */
    private fun showTutorial() {
        tutorialOpen = true
        feedback.muted = true
        binding.tutorial.visibility = View.VISIBLE
        tutorial.start()
    }

    private fun closeTutorial() {
        tutorialOpen = false
        tutorial.stop()
        binding.tutorial.visibility = View.GONE
        prefs().edit().putBoolean(PREF_TUTORIAL_SEEN, true).apply()
        if (!celebrating) feedback.muted = false
        requestCameraIfNeeded()
    }

    // ── 찾았어요! ───────────────────────────────────────────────────────────
    /**
     * 태스크 완료. 찾은 순간의 안경 사진을 가운데 띄우고 양옆에서 폭죽을
     * 터뜨린 뒤, 몇 초 있다가 전면 광고로 넘어간다 (기획서 14절: 성공했을 때만).
     *
     * 이 동안 추론과 음성·진동을 멈춘다. 멈추지 않으면 축하 화면과 광고
     * 위에서 "여기예요" 가 계속 나온다.
     */
    private fun onFound() {
        if (celebrating) return
        celebrating = true
        feedback.success()       // 음소거 직전에 부른다
        feedback.muted = true

        binding.btnFound.visibility = View.GONE
        binding.overlay.setTarget(null, Confidence.LOW, "")

        val img = snapshot
        if (img != null && !img.isRecycled) {
            binding.celebrateImage.setImageBitmap(img)
            binding.celebrateImage.visibility = View.VISIBLE
        } else {
            binding.celebrateImage.visibility = View.GONE
        }
        binding.celebration.visibility = View.VISIBLE
        binding.celebration.alpha = 0f
        binding.celebration.animate().alpha(1f).setDuration(220).start()
        binding.confetti.post { binding.confetti.burst() }
        // 한 번 더 — 첫 폭죽이 떨어질 즈음
        uiHandler.postDelayed({ binding.confetti.burst() }, 1100)

        uiHandler.postDelayed({
            ads.showInterstitial {
                binding.celebration.visibility = View.GONE
                binding.celebrateImage.setImageDrawable(null)
                resetSession()
                celebrating = false
                if (!tutorialOpen) feedback.muted = false
            }
        }, CELEBRATE_MS)
    }

    // ── 모델 ────────────────────────────────────────────────────────────────
    private fun extractedModel(asset: String): File? {
        val dst = File(filesDir, asset)
        if (dst.exists() && dst.length() > 0) return dst
        // 모델을 바꾸면 파일명을 바꾼다. 예전에 꺼내둔 모델은 50MB 라 지운다.
        filesDir.listFiles { f -> f.name.endsWith(".onnx") && f.name != asset }
            ?.forEach { it.delete() }
        return try {
            val tmp = File(filesDir, "$asset.part")
            assets.open(asset).use { input ->
                tmp.outputStream().use { out -> input.copyTo(out, 1 shl 20) }
            }
            if (tmp.renameTo(dst)) dst else { tmp.delete(); null }
        } catch (e: Throwable) {
            Log.e(TAG, "번들 모델 추출 실패: $asset", e)
            null
        }
    }

    private fun loadDetector(): Boolean {
        val entry = selectedModel
        val f = extractedModel(entry.asset) ?: return false
        return try {
            detector?.close()
            detector = null
            val t0 = System.currentTimeMillis()
            // NNAPI 를 먼저 시도하고 안 되면 CPU. SD685 에서는 둘이 비슷했다.
            val d = YoloDetector.create(f, entry.label, selectedSize, preferNnapi = true)
            d.targetClasses = target.classes
            detector = d
            Log.i(TAG, "${entry.label} ${selectedSize}px ${d.provider} " +
                "로드 ${System.currentTimeMillis() - t0}ms")
            true
        } catch (e: Throwable) {
            Log.e(TAG, "모델 로드 실패", e)
            false
        }
    }

    private fun loadDetectorAsync() {
        showLoading(getString(R.string.preparing))
        inferExecutor.execute {
            val ok = loadDetector()
            runOnUiThread {
                hideLoading()
                // 튜토리얼이 떠 있으면 카메라는 닫을 때 켠다
                if (ok && !tutorialOpen && ContextCompat.checkSelfPermission(
                        this, Manifest.permission.CAMERA
                    ) == PackageManager.PERMISSION_GRANTED
                ) startCamera()
            }
        }
    }

    private fun reloadDetector(msg: String) {
        resetSession()
        showLoading(msg)
        inferExecutor.execute {
            loadDetector()
            runOnUiThread { hideLoading() }
        }
    }

    private fun showLoading(text: String) {
        binding.loading.visibility = View.VISIBLE
        binding.loadingText.text = text
    }

    private fun hideLoading() {
        binding.loading.visibility = View.GONE
    }

    /**
     * 사용자 화질 선택. 폰 성능이 제각각이라 고르게 한다.
     * 416 아래는 실기기에서 검출이 거의 안 돼 선택지에서 뺐다.
     */
    private fun setupQuality() {
        val saved = prefs().getInt(PREF_INPUT_SIZE, selectedSize)
        if (ModelCatalog.QUALITIES.any { it.size == saved }) selectedSize = saved

        // "보통 · 416px" 처럼 알아들을 이름과 실제 크기를 같이 보여준다
        val items = ModelCatalog.QUALITIES.map { "${getString(it.labelRes)} · ${it.size}px" }
        val current = ModelCatalog.QUALITIES.indexOfFirst { it.size == selectedSize }
            .coerceAtLeast(0)

        binding.spQuality.adapter = android.widget.ArrayAdapter(
            this, R.layout.spinner_item_pill, items
        ).also { it.setDropDownViewResource(R.layout.spinner_dropdown_item) }
        binding.spQuality.setSelection(current, false)
        binding.spQuality.onItemSelectedListener =
            object : android.widget.AdapterView.OnItemSelectedListener {
                override fun onItemSelected(
                    p: android.widget.AdapterView<*>?, v: View?, pos: Int, id: Long,
                ) {
                    val size = ModelCatalog.QUALITIES[pos].size
                    if (size == selectedSize) return
                    selectedSize = size
                    prefs().edit().putInt(PREF_INPUT_SIZE, size).apply()
                    reloadDetector(getString(R.string.preparing))
                }

                override fun onNothingSelected(p: android.widget.AdapterView<*>?) = Unit
            }
    }

    // ── 카메라 ──────────────────────────────────────────────────────────────
    private fun startCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            val provider = future.get()

            // 프리뷰와 분석의 화면비를 같게 고정한다. 지정하지 않으면 CameraX 가
            // 각각 다르게 고를 수 있고, 그러면 오버레이가 상시 어긋난다.
            @Suppress("DEPRECATION")
            val ratio = androidx.camera.core.AspectRatio.RATIO_16_9

            @Suppress("DEPRECATION")
            val preview = Preview.Builder().setTargetAspectRatio(ratio).build().also {
                it.setSurfaceProvider(binding.previewView.surfaceProvider)
            }

            @Suppress("DEPRECATION")
            val analysis = ImageAnalysis.Builder()
                .setTargetAspectRatio(ratio)
                // 밀린 프레임은 버리고 항상 최신만 본다 (기획서 8절)
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                .build()
                .also { it.setAnalyzer(analysisExecutor, ::analyze) }

            provider.unbindAll()
            val camera = provider.bindToLifecycle(
                this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis
            )
            readCameraGeometry(camera.cameraInfo)
        }, ContextCompat.getMainExecutor(this))
    }

    /**
     * 실제 초점거리와 센서 크기를 읽는다.
     * 화각을 65도로 가정하면 자이로 보정량이 어긋난다. 핀홀 관계로 구한다.
     *   focal_px = focal_mm × (센서 프레임 가로 픽셀 / 센서 물리 가로 mm)
     */
    @androidx.annotation.OptIn(androidx.camera.camera2.interop.ExperimentalCamera2Interop::class)
    private fun readCameraGeometry(info: androidx.camera.core.CameraInfo) {
        try {
            val c2 = androidx.camera.camera2.interop.Camera2CameraInfo.from(info)
            focalMm = c2.getCameraCharacteristic(
                android.hardware.camera2.CameraCharacteristics
                    .LENS_INFO_AVAILABLE_FOCAL_LENGTHS
            )?.firstOrNull() ?: 0f
            sensorWidthMm = c2.getCameraCharacteristic(
                android.hardware.camera2.CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE
            )?.width ?: 0f
            Log.i(TAG, "focal=${focalMm}mm sensorW=${sensorWidthMm}mm")
        } catch (e: Throwable) {
            Log.w(TAG, "카메라 기하를 읽지 못했습니다: ${e.message}")
        }
    }

    /**
     * 분석 콜백. 30fps 로 들어온다.
     *
     * 추론이 도는 동안에도 프레임을 받아 패치 추적에 쓴다. 이전에는 추론이
     * 동기로 돌아 그 사이 20장을 그냥 버렸다.
     */
    private fun analyze(image: ImageProxy) {
        try {
            val rotation = image.imageInfo.rotationDegrees
            val iw = image.width
            val ih = image.height
            val fw = if (rotation % 180 == 0) iw else ih
            val fh = if (rotation % 180 == 0) ih else iw
            val captureR = latestR

            // 추적용 흑백 축소본. 비트맵을 거치지 않아 싸다.
            val grayOk = gray.fill(image, rotation)

            // 축하 화면·튜토리얼 중에는 추론하지 않는다 (발열도 줄인다)
            val free = !busy.get() && !celebrating && !tutorialOpen
            val bmp = if (free) image.toBitmap() else null
            image.close()

            if (focalMm > 0f && sensorWidthMm > 0f) {
                tracker.setCameraGeometry(focalMm * iw / sensorWidthMm, rotation, fw, fh)
            }

            // 추론이 막 끝났으면 템플릿을 다시 심는다 (gray 를 소유한 스레드다)
            if (grayOk && needsReseed) {
                needsReseed = false
                tracker.primary(System.currentTimeMillis())?.let { patch.seed(gray, it.box) }
            }

            // 이동 보정 — 추론을 기다리지 않고 매 프레임 반영한다
            else if (grayOk && patch.isActive) {
                patch.track(gray)?.let { (dx, dy) ->
                    tracker.applyVisualShift(dx, dy, latestR)
                }
            }

            if (free && bmp != null) {
                busy.set(true)
                inferExecutor.execute {
                    try {
                        runInference(bmp, rotation, fw, fh, captureR, grayOk)
                    } finally {
                        busy.set(false)
                    }
                }
            }

            publish(fw, fh)
        } catch (e: Throwable) {
            Log.e(TAG, "분석 실패", e)
        }
    }

    private fun runInference(
        bmp: android.graphics.Bitmap, rotation: Int, fw: Int, fh: Int,
        captureR: FloatArray?, grayOk: Boolean,
    ) {
        val d = detector ?: run { bmp.recycle(); return }
        val result = try {
            d.detect(bmp, rotation, THRESHOLD)
        } catch (e: Throwable) {
            Log.e(TAG, "추론 실패", e)
            bmp.recycle()
            return
        }

        // 세션 최고점을 갱신하면 그 순간의 안경 사진을 잘라둔다. 찾았을 때
        // 가운데 띄운다. 전체 프레임 회전이 들어가므로 갱신할 때만 한다.
        result.detections.maxByOrNull { it.score }?.let { top ->
            if (top.score > snapshotScore) {
                SnapshotCrop.crop(bmp, rotation, top.box)?.let { cut ->
                    snapshotScore = top.score
                    snapshot = cut
                }
            }
        }
        bmp.recycle()

        val now = System.currentTimeMillis()
        val fired = tracker.update(result.detections, now, captureR, latestR)

        val interval = result.inferenceMs + result.preprocessMs + result.postprocessMs
        tracker.setFrameIntervalMs(interval)
        if (interval > 0) {
            fps = 1000f / interval
            sweep.setFps(fps)
        }

        // 검출이 나온 자리로 추적 템플릿을 다시 심는다. 추적 오차가 쌓이는
        // 구간이 추론 한 주기로 제한된다. 실제 seed 는 분석 스레드에서 한다.
        needsReseed = true

        if (fired != null && !celebrating) {
            runOnUiThread { binding.btnFound.visibility = View.VISIBLE }
        }
    }

    /** 화면 갱신. 추론과 무관하게 자주 불린다. */
    private fun publish(fw: Int, fh: Int) {
        if (celebrating) return
        val now = System.currentTimeMillis()
        val t = tracker.primary(now)
        runOnUiThread {
            binding.overlay.setFrameSize(fw, fh)
            if (t == null) {
                binding.overlay.setTarget(null, Confidence.LOW, "")
                binding.hint.visibility = View.VISIBLE
                binding.hint.text = getString(
                    if (tooFast) R.string.too_fast else R.string.searching
                )
                feedback.onTarget(null, now)
            } else {
                val conf = Confidence.of(t.score)
                binding.overlay.setTarget(t.box, conf, getString(conf.messageRes))
                binding.hint.visibility = View.GONE
                // 변화가 있을 때만 말하고 떤다. 매 프레임 불러도 된다.
                feedback.onTarget(conf, now)
            }
        }
    }

    // ── 자이로 ──────────────────────────────────────────────────────────────
    override fun onResume() {
        super.onResume()
        val sm = getSystemService(SensorManager::class.java)
        sm.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)?.let {
            sm.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
        }
    }

    override fun onPause() {
        super.onPause()
        getSystemService(SensorManager::class.java).unregisterListener(this)
    }

    override fun onSensorChanged(event: SensorEvent) {
        if (event.sensor.type != Sensor.TYPE_ROTATION_VECTOR) return
        // azimuth/pitch 로 바꾸지 않는다. 폰을 아래로 눕히면 짐벌락 근처에서
        // 화면이 안 움직여도 azimuth 가 크게 튄다. 회전행렬을 그대로 쓴다.
        val r = FloatArray(9)
        SensorManager.getRotationMatrixFromVector(r, event.values)
        latestR = r

        val now = System.currentTimeMillis()
        // SweepGuide 가 히스테리시스를 건다. 켜지는 순간에만 알리고, 그마저도
        // Feedback 이 15초 간격으로 거른다.
        val fast = sweep.onRotation(r, now)
        if (fast && !tooFast && !celebrating) feedback.onTooFast(now)
        tooFast = fast

        if (celebrating) return

        // 센서 주기로 회전 보정. 추론이 0.7~1.9초라 이게 없으면 박스가 그 사이
        // 멈춰 있고, 폰이 움직이면 좌표가 틀린다.
        if (tracker.onRotation(r)) {
            val t = tracker.primary(now)
            binding.overlay.setTarget(
                t?.box,
                t?.let { Confidence.of(it.score) } ?: Confidence.LOW,
                t?.let { getString(Confidence.of(it.score).messageRes) } ?: "",
            )
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    override fun onDestroy() {
        super.onDestroy()
        uiHandler.removeCallbacksAndMessages(null)
        analysisExecutor.shutdown()
        inferExecutor.shutdown()
        detector?.close()
        feedback.shutdown()
        ads.destroy()
        purchases.end()
    }

    companion object {
        private const val TAG = "MainActivity"

        /** 검출 임계값. 실기기에서 0.05 가 맞았다 — 낮은 점수는 신뢰도 단계와 temporal filter 가 거른다 */
        private const val THRESHOLD = 0.05f

        /** docs/privacy/index.html 을 GitHub Pages 로 공개한 주소 (저장소 공개 후 유효) */
        private const val PRIVACY_POLICY_URL = "https://myaune.github.io/find-my-glasses/privacy/"

        private const val PREF_TUTORIAL_SEEN = "tutorial_seen"
        private const val PREF_INPUT_SIZE = "input_size"
        private const val PREF_VOICE = "voice"
        private const val PREF_VIBRATION = "vibration"

        /** 앱 언어 선택지. 이름은 그 언어로 쓴다 (못 읽는 언어로 바뀌어도 돌아올 수 있게). */
        private val LANGUAGES = listOf(
            "en" to "English",
            "ko" to "한국어",
            "zh-CN" to "简体中文",
            "zh-TW" to "繁體中文",
            "ja" to "日本語",
            "es" to "Español",
            "pt" to "Português",
            "fr" to "Français",
            "de" to "Deutsch",
            "it" to "Italiano",
            "ru" to "Русский",
            "tr" to "Türkçe",
            "ar" to "العربية",
            "hi" to "हिन्दी",
            "id" to "Bahasa Indonesia",
            "vi" to "Tiếng Việt",
            "th" to "ไทย",
        )

        /** 축하 화면을 보여준 뒤 광고로 넘어가기까지 */
        private const val CELEBRATE_MS = 2800L
    }
}
