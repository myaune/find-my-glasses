package com.myaune.findglasses

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.graphics.Bitmap
import android.graphics.RectF
import android.util.Log
import java.io.File

/**
 * ONNX Runtime 으로 도는 YOLO 계열 (YOLO-World / YOLOE).
 *
 * 어휘가 검출 헤드에 구워져 있어 런타임에 텍스트 인코더가 없다.
 * dynamic 으로 익스포트했으므로 입력 해상도를 생성 시점에 고른다.
 *
 * 출력은 [1, C, N]
 *   채널 0..3        박스 xywh — 입력 픽셀 기준, 정규화 아님
 *   채널 4..4+nc     클래스 점수 (sigmoid 적용됨)
 *   그 뒤            YOLOE(seg) 는 마스크 계수 32 채널이 더 붙는다
 *
 * nc 를 C-4 로 역산하면 YOLOE 에서 39개로 잘못 읽는다. CLASSES.size 를 쓴다.
 *
 * 라이선스: 모델 GPL-3.0, ultralytics AGPL-3.0. 앱 소스 공개 전제.
 */
class YoloDetector private constructor(
    private val env: OrtEnvironment,
    private val session: OrtSession,
    override val provider: String,
    override val modelBytes: Long,
    override val label: String,
    private val inputSize: Int,
) : Detector {

    private val preprocess = Preprocess(
        size = inputSize,
        padGray = ModelCatalog.PAD_GRAY,
        // YOLO 는 /255 만 한다. ImageNet 정규화를 넣으면 검출이 무너진다.
        mean = null,
        std = null,
    )
    private val inputName: String = session.inputNames.first()
    private val nc = ModelCatalog.CLASSES.size

    @Volatile
    override var targetClasses: IntArray = ModelCatalog.Target.GLASSES.classes

    override fun close() = session.close()

    override fun detect(src: Bitmap, rotationDegrees: Int, threshold: Float): DetectResult {
        val t0 = System.nanoTime()
        val (buffer, fit) = preprocess.run(src, rotationDegrees)
        val t1 = System.nanoTime()

        val s = inputSize.toLong()
        val tensor = OnnxTensor.createTensor(env, buffer, longArrayOf(1, 3, s, s))
        val out = tensor.use { session.run(mapOf(inputName to it)) }
        val t2 = System.nanoTime()

        val parsed = out.use { parse(it, fit, threshold) }
        val t3 = System.nanoTime()

        return DetectResult(
            detections = parsed.first,
            inferenceMs = (t2 - t1) / 1_000_000,
            preprocessMs = (t1 - t0) / 1_000_000,
            postprocessMs = (t3 - t2) / 1_000_000,
            topPositiveScore = parsed.second,
        )
    }

    private fun parse(
        out: OrtSession.Result,
        fit: Preprocess.Fit,
        threshold: Float,
    ): Pair<List<Detection>, Float> {
        val t = out[0] as OnnxTensor
        val anchors = t.info.shape[2].toInt()
        val buf = t.floatBuffer

        val raw = ArrayList<Detection>()
        var topPositive = 0f
        val targets = targetClasses

        for (i in 0 until anchors) {
            var bestClass = -1
            var bestScore = 0f
            var positiveScore = 0f

            for (c in 0 until nc) {
                val v = buf.get((4 + c) * anchors + i)
                if (c in targets && v > positiveScore) positiveScore = v
                if (v > bestScore) {
                    bestScore = v
                    bestClass = c
                }
            }
            if (positiveScore > topPositive) topPositive = positiveScore

            // 다른 어휘가 더 높으면 대상이 아니다. 안경을 찾을 때는 열쇠·컵 등이,
            // 열쇠를 찾을 때는 안경이 네거티브가 된다.
            if (bestClass !in targets || bestScore < threshold) continue

            raw.add(
                Detection(
                    bestScore,
                    toSourceRect(
                        buf.get(0 * anchors + i), buf.get(1 * anchors + i),
                        buf.get(2 * anchors + i), buf.get(3 * anchors + i), fit,
                    ),
                    bestClass,
                )
            )
        }

        raw.sortByDescending { it.score }
        return nms(raw) to topPositive
    }

    /** letterbox 입력 픽셀 xywh → 회전 보정된 원본 프레임 픽셀 */
    private fun toSourceRect(
        cx: Float, cy: Float, w: Float, h: Float, fit: Preprocess.Fit,
    ): RectF {
        var x1 = (cx - w / 2 - fit.padX) / fit.scale
        var y1 = (cy - h / 2 - fit.padY) / fit.scale
        var x2 = (cx + w / 2 - fit.padX) / fit.scale
        var y2 = (cy + h / 2 - fit.padY) / fit.scale
        x1 = x1.coerceIn(0f, fit.srcW.toFloat())
        x2 = x2.coerceIn(0f, fit.srcW.toFloat())
        y1 = y1.coerceIn(0f, fit.srcH.toFloat())
        y2 = y2.coerceIn(0f, fit.srcH.toFloat())
        return RectF(x1, y1, x2, y2)
    }

    /**
     * 같은 안경에 앵커 여러 개가 겹쳐 붙는다. 누르지 않으면 Tracker 가 이를
     * "여러 번 검출" 로 받아 단일 프레임만으로 발화한다. 기획서 9절의 3회는
     * 3개 프레임을 뜻한다.
     */
    private fun nms(sorted: List<Detection>, iouThreshold: Float = 0.3f): List<Detection> {
        val kept = ArrayList<Detection>()
        for (d in sorted) {
            if (kept.none { suppresses(it.box, d.box, iouThreshold) }) kept.add(d)
            if (kept.size >= MAX_DETECTIONS) break
        }
        return kept
    }

    /**
     * 이미 남긴 박스가 새 박스를 덮어쓰는가.
     *
     * IoU 만 보면 한 안경 위에 박스가 여러 개 남는다. 한쪽 렌즈만 잡은 것,
     * 양쪽을 잡은 것, 다리까지 포함한 것의 IoU 가 0.5 미만이라 다 살아남았다.
     * 그래서 포함 관계도 본다 — 작은 박스가 큰 박스 안에 대부분 들어가 있으면
     * 같은 물체로 보고 버린다.
     */
    private fun suppresses(kept: RectF, cand: RectF, iouThreshold: Float): Boolean {
        if (iou(kept, cand) >= iouThreshold) return true
        val ix = maxOf(0f, minOf(kept.right, cand.right) - maxOf(kept.left, cand.left))
        val iy = maxOf(0f, minOf(kept.bottom, cand.bottom) - maxOf(kept.top, cand.top))
        val inter = ix * iy
        val candArea = cand.width() * cand.height()
        if (candArea <= 0f) return true
        return inter / candArea >= CONTAINMENT
    }

    private fun iou(a: RectF, b: RectF): Float {
        val ix = maxOf(0f, minOf(a.right, b.right) - maxOf(a.left, b.left))
        val iy = maxOf(0f, minOf(a.bottom, b.bottom) - maxOf(a.top, b.top))
        val inter = ix * iy
        if (inter <= 0f) return 0f
        val union = a.width() * a.height() + b.width() * b.height() - inter
        return if (union > 0f) inter / union else 0f
    }

    companion object {
        private const val TAG = "YoloDetector"
        private const val MAX_DETECTIONS = 5

        /** 후보가 이미 남긴 박스 안에 이 비율 이상 들어가면 같은 물체로 본다. */
        private const val CONTAINMENT = 0.65f

        fun create(
            modelFile: File,
            label: String,
            inputSize: Int,
            preferNnapi: Boolean,
        ): YoloDetector {
            require(modelFile.exists()) { "모델 파일이 없습니다: ${modelFile.absolutePath}" }
            val env = OrtEnvironment.getEnvironment()

            if (preferNnapi) {
                try {
                    val opts = OrtSession.SessionOptions()
                    opts.addNnapi()
                    val s = env.createSession(modelFile.absolutePath, opts)
                    Log.i(TAG, "$label NNAPI")
                    return YoloDetector(env, s, "NNAPI", modelFile.length(), label, inputSize)
                } catch (e: Throwable) {
                    Log.w(TAG, "NNAPI 실패, CPU 로 전환: ${e.message}")
                }
            }

            val opts = OrtSession.SessionOptions()
            opts.setIntraOpNumThreads(4)   // Cortex-A73 ×4
            val s = env.createSession(modelFile.absolutePath, opts)
            Log.i(TAG, "$label CPU")
            return YoloDetector(env, s, "CPU", modelFile.length(), label, inputSize)
        }
    }
}
