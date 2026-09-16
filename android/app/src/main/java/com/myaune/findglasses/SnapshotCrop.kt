package com.myaune.findglasses

import android.graphics.Bitmap
import android.graphics.Matrix
import android.graphics.RectF
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * 찾았을 때 보여줄 안경 사진.
 *
 * 추론에 들어간 프레임에서 검출 박스 주변을 잘라낸다. 박스는 회전 보정된
 * 프레임 좌표이므로 원본을 먼저 회전시킨 뒤 자른다.
 *
 * 전체 프레임을 회전하는 게 싸지 않지만, 세션 최고점을 갱신할 때만 부르므로
 * 드물게 일어난다.
 */
object SnapshotCrop {

    /**
     * @param padRatio 박스 크기 대비 여백. 안경만 딱 자르면 어디인지 맥락이 없다.
     * @param maxSide 결과 긴 변 상한. 화면 가운데 띄우기엔 이 정도면 충분하다.
     */
    fun crop(
        src: Bitmap, rotationDegrees: Int, box: RectF,
        padRatio: Float = 0.6f, maxSide: Int = 720,
    ): Bitmap? = try {
        val rotated = if (rotationDegrees % 360 == 0) src else Bitmap.createBitmap(
            src, 0, 0, src.width, src.height,
            Matrix().apply { postRotate(rotationDegrees.toFloat()) }, true,
        )

        val padX = box.width() * padRatio
        val padY = box.height() * padRatio
        // 너무 작은 검출도 알아볼 수 있게 최소 크기를 준다
        val minSide = min(rotated.width, rotated.height) * 0.35f
        val cx = box.centerX()
        val cy = box.centerY()
        val halfW = max(box.width() / 2 + padX, minSide / 2)
        val halfH = max(box.height() / 2 + padY, minSide / 2)

        val l = (cx - halfW).roundToInt().coerceIn(0, rotated.width - 1)
        val t = (cy - halfH).roundToInt().coerceIn(0, rotated.height - 1)
        val r = (cx + halfW).roundToInt().coerceIn(l + 1, rotated.width)
        val b = (cy + halfH).roundToInt().coerceIn(t + 1, rotated.height)

        val cut = Bitmap.createBitmap(rotated, l, t, r - l, b - t)
        if (rotated !== src) rotated.recycle()

        val s = maxSide.toFloat() / max(cut.width, cut.height)
        if (s < 1f) {
            val out = Bitmap.createScaledBitmap(
                cut, (cut.width * s).roundToInt(), (cut.height * s).roundToInt(), true,
            )
            if (out !== cut) cut.recycle()
            out
        } else cut
    } catch (e: Throwable) {
        null
    }
}
