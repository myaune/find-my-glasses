package com.myaune.findglasses

import android.graphics.Bitmap
import android.graphics.RectF

/** 회전 보정된 원본 프레임 좌표(픽셀)를 가진 검출 하나. */
data class Detection(
    val score: Float,
    val box: RectF,
    val classIndex: Int,
)

data class DetectResult(
    val detections: List<Detection>,
    /** 순수 추론 시간. 전처리·후처리 제외 */
    val inferenceMs: Long,
    val preprocessMs: Long,
    val postprocessMs: Long,
    /** 임계값을 넘지 못해도 이 프레임의 최고 양성 점수. 임계값 튜닝용 */
    val topPositiveScore: Float,
)

interface Detector {
    val provider: String
    val modelBytes: Long
    val label: String
    /** 찾을 대상의 클래스 번호들 (ModelCatalog.CLASSES). 나머지는 네거티브 */
    var targetClasses: IntArray
    fun detect(src: Bitmap, rotationDegrees: Int, threshold: Float): DetectResult
    fun close()
}
