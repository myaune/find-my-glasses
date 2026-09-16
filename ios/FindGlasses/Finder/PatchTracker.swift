import CoreGraphics
import Foundation

/// 정규상관(NCC) 패치 추적 — 이동·시차까지 보정한다. Android `PatchTracker.kt` 의 이식.
///
/// 자이로는 자세만 준다. 근거리(0.3~1m)에서는 몸을 조금만 옮겨도 시차가 커서
/// 박스 주변 패치를 영상으로 직접 따라간다. 추론이 도는 동안 버려지던 프레임을 쓰고,
/// 추론이 끝나면 검출로 다시 심어 오차가 쌓이는 구간을 추론 한 주기로 제한한다.
/// 무늬 없는 면에서는 실패하고, 그때는 자이로에 맡긴다.
final class PatchTracker {

    private var template: [UInt8]?
    private var tw = 0
    private var th = 0
    /// 축소본 좌표계의 현재 패치 중심
    private var cx: CGFloat = 0
    private var cy: CGFloat = 0

    private(set) var lastScore: Float = 0
    var isActive: Bool { template != nil }

    private static let minPatch = 12
    private static let maxPatch = 40
    private static let search = 10
    private static let minScore: Float = 0.45
    private static let minContrast: Float = 6

    func clear() {
        template = nil
        lastScore = 0
    }

    /// 검출 결과로 템플릿을 새로 심는다. - Parameter box: 원본 프레임 좌표
    func seed(_ gray: GrayFrame, box: CGRect) {
        let s = gray.scale
        let ccx = box.midX / s
        let ccy = box.midY / s
        let w = Int((box.width / s).rounded()).clamped(Self.minPatch, Self.maxPatch)
        let h = Int((box.height / s).rounded()).clamped(Self.minPatch, Self.maxPatch)
        let x0 = Int((ccx - CGFloat(w) / 2).rounded())
        let y0 = Int((ccy - CGFloat(h) / 2).rounded())
        if x0 < 0 || y0 < 0 || x0 + w > gray.width || y0 + h > gray.height { clear(); return }

        var t = [UInt8](repeating: 0, count: w * h)
        for y in 0..<h {
            let src = (y0 + y) * gray.width + x0
            for x in 0..<w { t[y * w + x] = gray.data[src + x] }
        }
        // 특징이 거의 없는 패치는 추적해도 의미가 없다
        if stdDev(t) < Self.minContrast { clear(); return }
        template = t
        tw = w
        th = h
        cx = ccx
        cy = ccy
        lastScore = 1
    }

    /// - Returns: 원본 프레임 좌표의 (dx, dy). 실패하면 nil
    func track(_ gray: GrayFrame) -> (CGFloat, CGFloat)? {
        guard let t = template, tw <= gray.width, th <= gray.height else { return nil }

        let cxi = Int((cx - CGFloat(tw) / 2).rounded())
        let cyi = Int((cy - CGFloat(th) / 2).rounded())
        let xFrom = max(cxi - Self.search, 0)
        let xTo = min(cxi + Self.search, gray.width - tw)
        let yFrom = max(cyi - Self.search, 0)
        let yTo = min(cyi + Self.search, gray.height - th)
        if xFrom > xTo || yFrom > yTo { return nil }

        var bestScore: Float = -2
        var bestX = cxi
        var bestY = cyi
        gray.data.withUnsafeBufferPointer { img in
            t.withUnsafeBufferPointer { tp in
                for y in yFrom...yTo {
                    for x in xFrom...xTo {
                        let s = ncc(tp, img, gray.width, x, y)
                        if s > bestScore { bestScore = s; bestX = x; bestY = y }
                    }
                }
            }
        }

        lastScore = bestScore
        if bestScore < Self.minScore { return nil }

        let ncx = CGFloat(bestX) + CGFloat(tw) / 2
        let ncy = CGFloat(bestY) + CGFloat(th) / 2
        let dx = (ncx - cx) * gray.scale
        let dy = (ncy - cy) * gray.scale
        cx = ncx
        cy = ncy
        return (dx, dy)
    }

    /// 평균을 빼고 정규화한 상관. 밝기·대비가 바뀌어도 유지된다. -1..1
    private func ncc(_ t: UnsafeBufferPointer<UInt8>, _ img: UnsafeBufferPointer<UInt8>,
                     _ imgW: Int, _ ox: Int, _ oy: Int) -> Float {
        var sumT = 0, sumI = 0
        for y in 0..<th {
            let src = (oy + y) * imgW + ox
            for x in 0..<tw {
                sumT += Int(t[y * tw + x])
                sumI += Int(img[src + x])
            }
        }
        let n = Float(tw * th)
        let mT = Float(sumT) / n
        let mI = Float(sumI) / n
        var num: Float = 0, dT: Float = 0, dI: Float = 0
        for y in 0..<th {
            let src = (oy + y) * imgW + ox
            for x in 0..<tw {
                let a = Float(t[y * tw + x]) - mT
                let b = Float(img[src + x]) - mI
                num += a * b
                dT += a * a
                dI += b * b
            }
        }
        let den = (dT * dI).squareRoot()
        return den < 1e-3 ? -2 : num / den
    }

    private func stdDev(_ t: [UInt8]) -> Float {
        let m = Float(t.reduce(0) { $0 + Int($1) }) / Float(t.count)
        let v = t.reduce(Float(0)) { acc, b in let d = Float(b) - m; return acc + d * d }
        return (v / Float(t.count)).squareRoot()
    }
}
