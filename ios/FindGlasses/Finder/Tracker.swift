import CoreGraphics
import Foundation

/// 자이로 앵커링 + temporal filter. Android `Tracker.kt` 의 이식.
///
/// 추론이 1초 안팎이라 앵커링은 보조가 아니라 프레임 사이를 메우는 코어다.
/// - 촬영 순간의 회전행렬을 검출과 함께 저장하고 그 기준으로 계산한다
/// - 누적 오프셋이 아니라 앵커 회전 → 현재 회전의 절대 델타로 매번 다시 계산한다
/// - 병진 이동은 자이로로 보정하지 않는다 (영상 추적 [PatchTracker] 가 맡는다)
///
/// 회전행렬은 기기좌표 → 월드 (row-major 3×3). [Motion] 이 Android 와 같은 규약으로 만든다.
final class Tracker {

    struct Target {
        let box: CGRect
        let score: Float
        let fired: Bool
        let hits: Int
        let ageMs: Double
    }

    private final class Track {
        var anchorBox: CGRect
        var anchorR: [Float]
        var lastMs: Double
        var hits = 0
        var bestScore: Float = 0
        var fired = false
        var dx: CGFloat = 0
        var dy: CGFloat = 0

        init(anchorBox: CGRect, anchorR: [Float], lastMs: Double) {
            self.anchorBox = anchorBox
            self.anchorR = anchorR
            self.lastMs = lastMs
        }

        var displayBox: CGRect { anchorBox.offsetBy(dx: dx, dy: dy) }
    }

    private let lock = NSLock()
    private var tracks: [Track] = []
    private let hitsRequired = 2
    private let iouThreshold: CGFloat = 0.1

    /// 픽셀 초점거리. 0 이면 보정하지 않는다.
    private var focalPx: CGFloat = 0
    private var maxGapMs: Double = 3000

    private(set) var fireCount = 0

    private static let maxTracks = 3
    /// 중심 거리 허용치를 박스 최대변의 몇 배까지 볼 것인가
    private static let centerReach: CGFloat = 1.5
    private static let identity: [Float] = [1, 0, 0, 0, 1, 0, 0, 0, 1]

    func setFocal(_ px: CGFloat) {
        lock.lock(); defer { lock.unlock() }
        if px > 0 { focalPx = px }
    }

    /// 프레임 간격보다 짧으면 다음 검출 전에 트랙이 죽는다. 2배로 잡는다.
    func setFrameInterval(ms: Double) {
        lock.lock(); defer { lock.unlock() }
        maxGapMs = max(2500, ms * 2)
    }

    func reset() {
        lock.lock(); defer { lock.unlock() }
        tracks.removeAll()
        fireCount = 0
    }

    /// 제품 화면이 쓰는 단일 타깃. 발화한 트랙을 우선하고, 그다음 점수순.
    func primary(nowMs: Double) -> Target? {
        lock.lock(); defer { lock.unlock() }
        tracks.removeAll { nowMs - $0.lastMs > maxGapMs }
        guard let t = best() else { return nil }
        return Target(box: t.displayBox, score: t.bestScore, fired: t.fired, hits: t.hits, ageMs: nowMs - t.lastMs)
    }

    private func best() -> Track? {
        tracks.max { a, b in
            if a.fired != b.fired { return !a.fired }
            return a.bestScore < b.bestScore
        }
    }

    /// 영상 추적으로 얻은 이동량. 영상 이동에는 회전분까지 들어 있으므로 자이로
    /// 보정량과 더하지 않고, 자이로 기준을 현재로 갱신한다 (이중 계산 방지).
    func applyVisualShift(dx: CGFloat, dy: CGFloat, rNow: [Float]?) {
        lock.lock(); defer { lock.unlock() }
        guard let t = best() else { return }
        t.anchorBox = t.anchorBox.offsetBy(dx: dx, dy: dy)
        t.dx = 0
        t.dy = 0
        if let r = rNow { t.anchorR = r }
    }

    /// 센서 주기로 호출. - Returns: 화면을 갱신할 만큼 변했는가
    @discardableResult
    func onRotation(_ rNow: [Float]) -> Bool {
        lock.lock(); defer { lock.unlock() }
        return rotateLocked(rNow)
    }

    private func rotateLocked(_ rNow: [Float]) -> Bool {
        if tracks.isEmpty || focalPx <= 0 { return false }
        var changed = false
        for t in tracks {
            let (dx, dy) = pixelShift(anchor: t.anchorR, now: rNow)
            if abs(dx - t.dx) > 0.5 || abs(dy - t.dy) > 0.5 { changed = true }
            t.dx = dx
            t.dy = dy
        }
        return changed
    }

    /// 앵커 시점의 박스 중심이 지금 화면의 어디로 갔는가.
    /// M = R_now^T · R_anchor 로 광축 (0,0,-1) 을 옮긴 뒤 나눗셈으로 투영한다 (f·tanθ).
    /// 기기 축: X 오른쪽, Y 위, Z 화면 밖. 카메라는 -Z. 이미지 y 는 아래로 증가.
    private func pixelShift(anchor: [Float], now: [Float]) -> (CGFloat, CGFloat) {
        var m = [Float](repeating: 0, count: 9)
        for i in 0..<3 {
            for j in 0..<3 {
                var s: Float = 0
                for k in 0..<3 { s += now[k * 3 + i] * anchor[k * 3 + j] }
                m[i * 3 + j] = s
            }
        }
        let dx0 = -m[2], dy0 = -m[5], dz0 = -m[8]
        if dz0 >= -1e-3 { return (0, 0) }  // 카메라 뒤로 넘어갔다
        return (focalPx * CGFloat(dx0 / -dz0), -focalPx * CGFloat(dy0 / -dz0))
    }

    /// 추론 결과를 트랙에 붙인다. - Returns: 이번에 새로 발화한 박스
    @discardableResult
    func update(_ dets: [Detection], nowMs: Double, captureR: [Float]?, rNow: [Float]?) -> CGRect? {
        lock.lock(); defer { lock.unlock() }
        tracks.removeAll { nowMs - $0.lastMs > maxGapMs }
        if let r = rNow { _ = rotateLocked(r) }

        var fired: CGRect?
        var used = Set<ObjectIdentifier>()

        for d in dets {
            let candidates = tracks.filter { !used.contains(ObjectIdentifier($0)) }
            let t = candidates.max { similarity($0.displayBox, d.box) < similarity($1.displayBox, d.box) }
            if let t, similarity(t.displayBox, d.box) > 0 {
                // 새 검출을 새 앵커로 갈아끼운다. 오차가 쌓이지 않는다.
                t.anchorBox = d.box
                if let r = captureR { t.anchorR = r }
                t.dx = 0
                t.dy = 0
                t.lastMs = nowMs
                t.hits += 1
                used.insert(ObjectIdentifier(t))
                if d.score > t.bestScore { t.bestScore = d.score }
                if !t.fired && t.hits >= hitsRequired {
                    t.fired = true
                    fireCount += 1
                    fired = d.box
                }
            } else {
                let n = Track(anchorBox: d.box, anchorR: captureR ?? Self.identity, lastMs: nowMs)
                n.hits = 1
                n.bestScore = d.score
                used.insert(ObjectIdentifier(n))
                tracks.append(n)
            }
        }

        if tracks.count > Self.maxTracks {
            tracks.sort { $0.lastMs > $1.lastMs }
            tracks.removeLast(tracks.count - Self.maxTracks)
        }
        return fired
    }

    /// 같은 물체인가. IoU 가 0 이어도 중심이 가까우면 같은 것으로 본다.
    private func similarity(_ a: CGRect, _ b: CGRect) -> CGFloat {
        let i = iou(a, b)
        if i >= iouThreshold { return i + 1 }
        let dist = hypot(a.midX - b.midX, a.midY - b.midY)
        let reach = max(max(a.width, a.height), max(b.width, b.height)) * Self.centerReach
        return dist < reach ? 1 - dist / reach : 0
    }
}
