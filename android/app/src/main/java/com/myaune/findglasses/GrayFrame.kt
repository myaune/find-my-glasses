package com.myaune.findglasses

import androidx.camera.core.ImageProxy

/**
 * 카메라 프레임에서 회전 보정된 흑백 축소본을 뽑는다.
 *
 * 추적에만 쓰므로 작게 만든다. 비트맵을 거치지 않고 RGBA 버퍼를 바로 샘플링해
 * 할당 없이 끝낸다 — 추론이 도는 동안 30fps 로 호출되는 경로다.
 *
 * 좌표계는 검출 박스와 같은 "회전 보정된 프레임" 이다. 그래야 추적으로 얻은
 * 이동량을 박스에 그대로 더할 수 있다.
 */
class GrayFrame(private val targetLongSide: Int = 192) {

    var data: ByteArray = ByteArray(0)
        private set
    var width = 0
        private set
    var height = 0
        private set

    /** 축소본 1픽셀이 회전 보정된 원본 프레임의 몇 픽셀인가 */
    var scale = 1f
        private set

    /**
     * @param rotationDegrees ImageProxy.imageInfo.rotationDegrees
     * @return 성공 여부
     */
    fun fill(image: ImageProxy, rotationDegrees: Int): Boolean {
        val plane = image.planes.firstOrNull() ?: return false
        val buf = plane.buffer
        val rowStride = plane.rowStride
        val pixStride = plane.pixelStride
        val srcW = image.width
        val srcH = image.height

        // 회전 보정 후의 크기
        val rot = ((rotationDegrees % 360) + 360) % 360
        val swap = rot == 90 || rot == 270
        val outFullW = if (swap) srcH else srcW
        val outFullH = if (swap) srcW else srcH

        val step = maxOf(1, maxOf(outFullW, outFullH) / targetLongSide)
        val w = outFullW / step
        val h = outFullH / step
        if (w < 8 || h < 8) return false

        if (data.size != w * h) data = ByteArray(w * h)
        width = w
        height = h
        scale = step.toFloat()

        // 출력 (x, y) → 회전 보정 좌표 → 센서 좌표
        var i = 0
        for (y in 0 until h) {
            val oy = y * step
            for (x in 0 until w) {
                val ox = x * step
                val sx: Int
                val sy: Int
                when (rot) {
                    90 -> { sx = oy; sy = srcH - 1 - ox }
                    180 -> { sx = srcW - 1 - ox; sy = srcH - 1 - oy }
                    270 -> { sx = srcW - 1 - oy; sy = ox }
                    else -> { sx = ox; sy = oy }
                }
                val p = sy * rowStride + sx * pixStride
                if (p < 0 || p + 2 >= buf.limit()) {
                    data[i++] = 0
                    continue
                }
                val r = buf.get(p).toInt() and 0xFF
                val g = buf.get(p + 1).toInt() and 0xFF
                val b = buf.get(p + 2).toInt() and 0xFF
                // 정수 근사 휘도. 추적용이라 정확할 필요가 없다.
                data[i++] = (((r * 77 + g * 150 + b * 29) shr 8) and 0xFF).toByte()
            }
        }
        return true
    }
}
