package com.myaune.findglasses

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.Rect
import java.nio.FloatBuffer

/**
 * 카메라 프레임을 모델 입력 텐서로 바꾼다.
 *
 * 데스크탑 쪽 전처리와 같은 동작을 해야 한다. 여기가 어긋나면 "폰에서 안
 * 잡힌다" 가 모델 탓인지 전처리 탓인지 구분되지 않는다.
 *
 * 모델마다 다른 부분이 있어 인자로 받는다.
 *   Grounding DINO  패딩 0,   /255 후 ImageNet 평균·표준편차
 *   YOLO-World      패딩 114, /255 만
 */
class Preprocess(
    private val size: Int,
    private val padGray: Int = 0,
    private val mean: FloatArray? = null,
    private val std: FloatArray? = null,
) {

    /** letterbox 파라미터. 박스를 원본 좌표로 되돌릴 때 쓴다. */
    data class Fit(val scale: Float, val padX: Int, val padY: Int,
                   val srcW: Int, val srcH: Int)

    private val canvasBitmap: Bitmap =
        Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
    private val canvas = Canvas(canvasBitmap)
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG)
    private val padColor = Color.rgb(padGray, padGray, padGray)

    // 매 프레임 새로 할당하면 GC 가 돌아 레이턴시 측정이 흔들린다. 재사용한다.
    private val pixels = IntArray(size * size)
    private val chw = FloatArray(3 * size * size)
    private val buffer: FloatBuffer = FloatBuffer.allocate(3 * size * size)

    /**
     * @param src 회전 보정 전 비트맵
     * @param rotationDegrees ImageProxy.imageInfo.rotationDegrees
     */
    fun run(src: Bitmap, rotationDegrees: Int): Pair<FloatBuffer, Fit> {
        val rotated = if (rotationDegrees % 360 == 0) src else rotate(src, rotationDegrees)
        val w = rotated.width
        val h = rotated.height

        val scale = size.toFloat() / maxOf(w, h)
        // 데스크탑이 round 를 쓴다. 절삭하면 1px 어긋난다.
        val nw = Math.round(w * scale).coerceAtLeast(1)
        val nh = Math.round(h * scale).coerceAtLeast(1)
        val padX = (size - nw) / 2
        val padY = (size - nh) / 2

        canvas.drawColor(padColor)
        canvas.drawBitmap(rotated, null, Rect(padX, padY, padX + nw, padY + nh), paint)
        if (rotated !== src) rotated.recycle()

        canvasBitmap.getPixels(pixels, 0, size, 0, 0, size, size)

        val plane = size * size
        if (mean != null && std != null) {
            for (i in 0 until plane) {
                val p = pixels[i]
                chw[i] = (((p shr 16) and 0xFF) / 255f - mean[0]) / std[0]
                chw[plane + i] = (((p shr 8) and 0xFF) / 255f - mean[1]) / std[1]
                chw[2 * plane + i] = ((p and 0xFF) / 255f - mean[2]) / std[2]
            }
        } else {
            for (i in 0 until plane) {
                val p = pixels[i]
                chw[i] = ((p shr 16) and 0xFF) / 255f
                chw[plane + i] = ((p shr 8) and 0xFF) / 255f
                chw[2 * plane + i] = (p and 0xFF) / 255f
            }
        }

        buffer.clear()
        buffer.put(chw)
        buffer.rewind()

        return buffer to Fit(scale, padX, padY, w, h)
    }

    private fun rotate(src: Bitmap, degrees: Int): Bitmap {
        val m = Matrix().apply { postRotate(degrees.toFloat()) }
        return Bitmap.createBitmap(src, 0, 0, src.width, src.height, m, true)
    }
}
