import Foundation

/// 스윕 속도 안내. Android `SweepGuide.kt`.
///
/// 프레임 간 화면이 겹쳐야 하므로 프레임당 회전이 화각의 절반을 넘지 않아야 한다.
///   한계 = 32도 × FPS   (1.5 FPS → 48°/s)
/// 켜는 기준(한계)과 끄는 기준(한계의 70%)을 달리해 경계에서 음성이 반복되지 않게 한다.
final class SweepGuide {

    private var lastR: [Float]?
    private var lastMs: Double = 0

    private(set) var degPerSec: Float = 0
    private(set) var limitDegPerSec: Float = 48
    private(set) var tooFast = false

    private static let halfFovDeg: Float = 32
    private static let exitRatio: Float = 0.7

    func setFps(_ fps: Float) {
        if fps > 0.05 { limitDegPerSec = (Self.halfFovDeg * fps).clamped(10, 90) }
    }

    func reset() {
        lastR = nil
        degPerSec = 0
        tooFast = false
    }

    /// - Returns: 너무 빠른가 (히스테리시스 적용)
    func onRotation(_ r: [Float], nowMs: Double) -> Bool {
        let raw = measure(r, nowMs: nowMs)
        tooFast = tooFast ? raw > limitDegPerSec * Self.exitRatio : raw > limitDegPerSec
        return tooFast
    }

    private func measure(_ r: [Float], nowMs: Double) -> Float {
        let prev = lastR
        let prevMs = lastMs
        lastR = r
        lastMs = nowMs
        guard let prev, nowMs > prevMs else { return degPerSec }
        let dt = Float((nowMs - prevMs) / 1000)
        if dt < 1e-3 { return degPerSec }

        // 회전 델타의 각도 = acos((trace(M) - 1) / 2)
        var trace: Float = 0
        for i in 0..<3 {
            for k in 0..<3 { trace += r[k * 3 + i] * prev[k * 3 + i] }
        }
        let cosA = ((trace - 1) / 2).clamped(-1, 1)
        let deg = acos(cosA) * 180 / .pi
        degPerSec += (deg / dt - degPerSec) * 0.25  // EMA
        return degPerSec
    }
}
