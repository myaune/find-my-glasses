package com.myaune.findglasses

import android.graphics.RectF
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min

/**
 * 자이로 앵커링 + temporal filter (기획서 4·9절).
 *
 * SD685 에서 추론이 1.4~1.9초다. 그러면 앵커링은 "화면 밖으로 나갔을 때
 * 방향 유지" 용 보조 기능이 아니라 **프레임 사이를 메우는 코어**가 된다.
 *
 * 1차 구현이 크게 어긋났고 원인이 세 개였다.
 *
 * ① 기준 시점이 틀렸다
 *    촬영(t=0)과 트랙 생성(t=1.9s) 사이의 움직임이 통째로 빠졌다. 지금은
 *    촬영 순간의 회전행렬을 검출과 함께 저장하고 그 기준으로 계산한다.
 *
 * ② azimuth/pitch 를 썼다
 *    getOrientation() 의 azimuth 는 월드 수직축 기준이라, 폰을 아래로 눕히면
 *    짐벌락 근처에서 화면이 안 움직여도 값이 크게 튄다. 안경 찾기는 대부분
 *    내려다보는 자세다. 지금은 회전행렬 델타를 기기 좌표계에서 직접 쓴다.
 *
 * ③ 초점거리를 회전 후 너비 + 화각 65도 가정으로 계산했다
 *    세로로 들면 짧은 변이라 과소추정되어 보정량이 부족했다. 지금은
 *    카메라 특성(초점거리 mm, 센서 물리 크기)에서 픽셀 초점거리를 받는다.
 *
 * 누적 오프셋이 아니라 **앵커 회전에서 현재 회전까지의 절대 델타**로 매번
 * 다시 계산한다. 그래야 드리프트가 쌓이지 않는다.
 *
 * 남은 근사: 병진 이동(걸어다니기)은 보상하지 않는다. 회전이 지배적이라는
 * 가정이고, 틀리면 측정에서 드러난다.
 */
class Tracker(
    private val hitsRequired: Int = 2,
    private val iouThreshold: Float = 0.1f,
) {
    private class Track(
        var anchorBox: RectF,
        /** 이 박스가 촬영된 순간의 기기 회전 (device→world, row-major 3x3) */
        var anchorR: FloatArray,
        var lastMs: Long,
    ) {
        var hits = 0
        var bestScore = 0f
        var fired = false
        /** 앵커 회전에서 현재까지의 보정량 (회전 보정된 이미지 픽셀) */
        var dx = 0f
        var dy = 0f
        val displayBox: RectF
            get() = RectF(
                anchorBox.left + dx, anchorBox.top + dy,
                anchorBox.right + dx, anchorBox.bottom + dy,
            )
    }

    private val tracks = ArrayList<Track>()

    /** 픽셀 초점거리. 카메라 특성에서 받는다. 0 이면 보정하지 않는다. */
    private var focalPx = 0f

    /** ImageProxy.imageInfo.rotationDegrees. 센서 축 → 화면 축 변환에 쓴다. */
    private var rotationDegrees = 0

    /** 회전 보정된(화면) 프레임 크기. 광선 투영의 주점 계산에 쓴다. */
    private var frameW = 0
    private var frameH = 0

    private var maxGapMs: Long = 3000

    var firedAtMs: Long? = null
        private set
    var fireCount: Int = 0
        private set

    /** 마지막으로 계산된 보정량. 진단 표시용. */
    var lastDx = 0f
        private set
    var lastDy = 0f
        private set

    fun setCameraGeometry(focalPixels: Float, rotationDeg: Int, w: Int, h: Int) {
        if (focalPixels > 0f) focalPx = focalPixels
        rotationDegrees = ((rotationDeg % 360) + 360) % 360
        if (w > 0 && h > 0) { frameW = w; frameH = h }
    }

    fun setFrameIntervalMs(ms: Long) {
        // 프레임 간격보다 짧으면 다음 검출 전에 트랙이 죽어 발화가 영구히 0 이 된다.
        // 너무 길면 낡은 박스가 쌓인다. 2배로 잡는다.
        maxGapMs = max(2500L, ms * 2)
    }

    @Synchronized
    fun reset() {
        tracks.clear()
        firedAtMs = null
        fireCount = 0
        lastDx = 0f
        lastDy = 0f
    }

    /** 화면에 그릴 (앵커된 박스, 점수, 발화여부). 점수 높은 것부터. */
    @Synchronized
    fun anchoredBoxes(nowMs: Long): List<Triple<RectF, Float, Boolean>> {
        tracks.removeAll { nowMs - it.lastMs > maxGapMs }
        return tracks.sortedByDescending { it.bestScore }
            .take(MAX_DISPLAY)
            .map { Triple(it.displayBox, it.bestScore, it.fired) }
    }

    /**
     * 제품 화면이 쓰는 단일 타깃.
     *
     * 안경은 하나다. 여러 개를 띄우면 "어디지" 를 알려주는 목적에 오히려
     * 방해가 된다. 가장 믿을 만한 트랙 하나만 내보낸다.
     */
    @Synchronized
    fun primary(nowMs: Long): Target? {
        tracks.removeAll { nowMs - it.lastMs > maxGapMs }
        // 발화한 트랙을 우선하고, 그다음 점수순
        val t = tracks.maxWithOrNull(
            compareBy({ if (it.fired) 1 else 0 }, { it.bestScore })
        ) ?: return null
        return Target(t.displayBox, t.bestScore, t.fired, t.hits, nowMs - t.lastMs)
    }

    data class Target(
        val box: RectF,
        val score: Float,
        val fired: Boolean,
        val hits: Int,
        /** 마지막 실제 검출로부터 지난 시간 */
        val ageMs: Long,
    )

    /**
     * 영상 추적으로 얻은 이동량을 반영한다.
     *
     * 영상 추적의 dx 는 프레임 간 **전체 화면 이동**이라 회전으로 생긴 움직임까지
     * 이미 들어 있다. 여기에 자이로 보정량(t.dx)을 더하면 같은 구간의 같은 회전을
     * 두 번 세게 된다. 처음에 그렇게 짰다가 "회전이 다시 빨라진" 느낌이 났다.
     *
     * 그래서 영상 추적이 성공한 프레임에서는 영상 이동량만 쓰고, 자이로는 기준을
     * 현재로 갱신해 다음 영상 프레임까지의 짧은 구간(~33ms)만 메우게 한다.
     *   영상 = 보정 (회전+이동+시차)
     *   자이로 = 그 사이 보간 (회전만)
     *
     * 추적이 몇 프레임 실패했다가 돌아와도 맞다. 실패하는 동안 패치 중심은
     * 갱신되지 않으므로 돌아온 순간의 dx 는 마지막 성공 이후 전체 이동이고,
     * 자이로 기준도 그 시점부터 쌓였다. 영상 쪽으로 교체하면 된다.
     */
    @Synchronized
    fun applyVisualShift(dx: Float, dy: Float, rNow: FloatArray?) {
        val t = tracks.maxWithOrNull(
            compareBy({ if (it.fired) 1 else 0 }, { it.bestScore })
        ) ?: return
        t.anchorBox.offset(dx, dy)
        t.dx = 0f
        t.dy = 0f
        if (rNow != null) t.anchorR = rNow.copyOf()
    }

    /**
     * 센서 주기로 호출. 각 트랙의 앵커 회전 대비 현재 회전으로 보정량을 다시 계산.
     * @param rNow device→world 회전행렬 (SensorManager 규약, row-major 3x3)
     * @return 화면을 갱신할 만큼 변했는가
     */
    @Synchronized
    fun onRotation(rNow: FloatArray): Boolean {
        if (tracks.isEmpty() || focalPx <= 0f) return false
        var changed = false
        for (t in tracks) {
            val (dx, dy) = pixelShift(t.anchorR, rNow)
            if (abs(dx - t.dx) > 0.5f || abs(dy - t.dy) > 0.5f) changed = true
            t.dx = dx
            t.dy = dy
        }
        tracks.firstOrNull()?.let { lastDx = it.dx; lastDy = it.dy }
        return changed
    }

    /**
     * 앵커 시점의 박스 중심이 지금 화면의 어디로 갔는가.
     *
     * 1차 구현은 회전벡터로 선형 근사했다 (dx = -f·w_y). 방향은 맞는데 양이
     * 절반쯤 부족했다. 실제 이동량은 f·tan(θ) 인데 f·sin(θ) 를 계산했기
     * 때문이다 (1/cos(θ) 만큼 부족).
     *
     * 그래서 광축 방향을 M 으로 회전시킨 뒤 나눗셈으로 투영한다. 나눗셈이
     * 들어가므로 tan 이 되어 회전이 커도 정확하다.
     *
     * 그리고 rotationDegrees 만큼 2D 회전을 한 번 더 걸던 것을 없앴다. 그게
     * 방향을 90도 틀어놓은 진짜 원인이었다 (위로 돌리면 박스가 왼쪽으로).
     *
     * M = R_now^T · R_anchor 는 앵커 시점 기기좌표의 방향을 현재 기기좌표로
     * 옮기는 회전이다. 기기 축은 X 오른쪽, Y 위, Z 화면 밖이고 카메라는 -Z 를
     * 본다. 이미지 y 는 아래로 증가하므로 Y 부호만 뒤집으면 끝이다.
     *
     * 광축 기준 근사이므로 안경이 화면 가장자리에 있을 때는 보정량이 조금
     * 모자란다. 이 앱에는 그 정도면 충분하다.
     */
    private fun pixelShift(rAnchor: FloatArray, rNow: FloatArray): Pair<Float, Float> {
        // M = R_now^T · R_anchor
        val m = FloatArray(9)
        for (i in 0..2) for (j in 0..2) {
            var s = 0f
            for (k in 0..2) s += rNow[k * 3 + i] * rAnchor[k * 3 + j]
            m[i * 3 + j] = s
        }

        // 앵커 시점의 광축 방향 (0,0,-1) 을 현재 기기좌표로 옮긴다.
        // d = M · (0,0,-1) = -(M 의 3번째 열)
        val dx0 = -m[2]
        val dy0 = -m[5]
        val dz0 = -m[8]

        // 카메라 뒤로 넘어갔으면 보정을 포기한다
        if (dz0 >= -1e-3f) return 0f to 0f

        // 투영. 이미지 y 는 아래로 증가하므로 Y 부호를 뒤집는다.
        // 나눗셈이 들어가므로 tan 이 되고, 회전이 커도 정확하다.
        //
        // rotationDegrees 만큼 2D 회전을 한 번 더 걸고 있었는데 그게 군더더기였다.
        // M 은 기기 좌표계이고, 회전 보정된(똑바로 세운) 이미지 축은 이미 기기
        // 축과 일치한다 (x 오른쪽 = 기기 X, y 아래 = 기기 -Y). rotationDegrees 는
        // 센서 버퍼 축 → 기기 축 변환용인데 버퍼 축은 쓰지 않는다.
        //
        // 그 여분 회전(90도) 때문에 위로 돌리면 박스가 왼쪽으로 갔다.
        //   올바른 값  (0, +f·tanα)      아래로
        //   여분 회전  (-f·tanα, 0)      왼쪽으로
        return (focalPx * dx0 / -dz0) to (-focalPx * dy0 / -dz0)
    }

    /**
     * 추론 결과를 트랙에 붙인다.
     *
     * @param captureR 이 프레임이 촬영된 순간의 회전행렬
     * @return 이번에 새로 발화한 트랙의 박스. 없으면 null
     */
    @Synchronized
    fun update(
        dets: List<Detection>,
        nowMs: Long,
        captureR: FloatArray?,
        rNow: FloatArray?,
    ): RectF? {
        tracks.removeAll { nowMs - it.lastMs > maxGapMs }
        if (rNow != null) onRotation(rNow)

        var fired: RectF? = null
        val used = HashSet<Track>()

        for (d in dets) {
            // 앵커된 현재 위치와 비교해야 한다. 앵커 원본과 비교하면 어긋난다.
            val t = tracks.filter { it !in used }.maxByOrNull { similarity(it.displayBox, d.box) }

            if (t != null && similarity(t.displayBox, d.box) > 0f) {
                // 새 검출을 새 앵커로 갈아끼운다. 오차가 쌓이지 않는다.
                t.anchorBox = RectF(d.box)
                if (captureR != null) t.anchorR = captureR.copyOf()
                t.dx = 0f
                t.dy = 0f
                t.lastMs = nowMs
                t.hits++
                used.add(t)
                if (d.score > t.bestScore) t.bestScore = d.score
                if (!t.fired && t.hits >= hitsRequired) {
                    t.fired = true
                    fireCount++
                    if (firedAtMs == null) firedAtMs = nowMs
                    fired = RectF(d.box)
                }
            } else {
                tracks.add(
                    Track(RectF(d.box), captureR?.copyOf() ?: FloatArray(9) { if (it % 4 == 0) 1f else 0f }, nowMs)
                        .also {
                            it.hits = 1
                            it.bestScore = d.score
                            used.add(it)
                        }
                )
            }
        }

        // 트랙이 무한정 쌓이지 않게 자른다. 찾는 건 안경 하나다.
        if (tracks.size > MAX_TRACKS) {
            tracks.sortByDescending { it.lastMs }
            while (tracks.size > MAX_TRACKS) tracks.removeAt(tracks.size - 1)
        }
        return fired
    }

    /**
     * 같은 물체인가. IoU 가 0 이어도 중심이 가까우면 같은 것으로 본다.
     *
     * 프레임 간격이 1.9초라 물체가 박스 크기만큼 움직이는 일이 흔하다. IoU
     * 하나로만 보면 매번 새 트랙이 생겨 화면에 네모가 여러 개 쌓인다.
     */
    private fun similarity(a: RectF, b: RectF): Float {
        val i = iou(a, b)
        if (i >= iouThreshold) return i + 1f     // IoU 로 붙은 쪽을 우선
        val dcx = a.centerX() - b.centerX()
        val dcy = a.centerY() - b.centerY()
        val dist = hypot(dcx, dcy)
        val reach = max(max(a.width(), a.height()), max(b.width(), b.height())) * CENTER_REACH
        return if (dist < reach) 1f - dist / reach else 0f
    }

    private fun iou(a: RectF, b: RectF): Float {
        val ix = max(0f, min(a.right, b.right) - max(a.left, b.left))
        val iy = max(0f, min(a.bottom, b.bottom) - max(a.top, b.top))
        val inter = ix * iy
        if (inter <= 0f) return 0f
        val union = a.width() * a.height() + b.width() * b.height() - inter
        return if (union > 0f) inter / union else 0f
    }

    companion object {
        private const val MAX_TRACKS = 3
        // 디버그 화면에서만 여러 개를 본다. 제품은 primary() 하나만 쓴다.
        private const val MAX_DISPLAY = 3
        /** 중심 거리 허용치를 박스 최대변의 몇 배까지 볼 것인가 */
        private const val CENTER_REACH = 1.5f
    }
}
