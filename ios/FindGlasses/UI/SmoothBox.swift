import CoreGraphics
import Foundation

/// 화면에 그리는 네모를 부드럽게 따라가게 한다. 표시용일 뿐 추적 좌표는 건드리지 않는다.
/// Android `SmoothBox.kt` — One Euro 필터 (Casiez 2012).
///
/// 고정 lerp 는 회전 중에도 뒤처져 앵커링이 어긋나 보인다. One Euro 는 빠르게 움직일 때는
/// 거의 그대로 따라가고, 거의 멈춰 있을 때의 점프(추론 반영)만 부드럽게 미끄러진다.
final class SmoothBox {

    private var cx = OneEuro()
    private var cy = OneEuro()
    private var w = OneEuro()
    private var h = OneEuro()
    private var last: CFTimeInterval = 0

    /// 멈춰 있을 때의 차단 주파수. 1.5Hz 면 점프가 약 0.3초에 걸쳐 미끄러진다.
    private static let minCutoffHz: CGFloat = 1.5
    /// 속도에 따라 얼마나 빨리 따라갈지 (화면 폭/초 단위)
    private static let beta: CGFloat = 6
    private static let dCutoffHz: CGFloat = 1

    func reset() { last = 0 }

    func update(_ target: CGRect, viewWidth: CGFloat, now: CFTimeInterval) -> CGRect {
        let s = max(viewWidth, 1)
        if last == 0 {
            // 처음 나타날 때는 허공에서 날아오지 않고 그 자리에 뜬다
            cx.snap(target.midX / s); cy.snap(target.midY / s)
            w.snap(target.width / s); h.snap(target.height / s)
        } else {
            let dt = CGFloat(now - last).clamped(1e-4, 0.1)
            cx.filter(target.midX / s, dt); cy.filter(target.midY / s, dt)
            w.filter(target.width / s, dt); h.filter(target.height / s, dt)
        }
        last = now
        let hw = w.value * s / 2, hh = h.value * s / 2
        return CGRect(x: cx.value * s - hw, y: cy.value * s - hh, width: hw * 2, height: hh * 2)
    }

    private struct OneEuro {
        var value: CGFloat = 0
        var deriv: CGFloat = 0

        mutating func snap(_ x: CGFloat) { value = x; deriv = 0 }

        mutating func filter(_ x: CGFloat, _ dt: CGFloat) {
            deriv += alpha(SmoothBox.dCutoffHz, dt) * ((x - value) / dt - deriv)
            let cutoff = SmoothBox.minCutoffHz + SmoothBox.beta * abs(deriv)
            value += alpha(cutoff, dt) * (x - value)
        }

        private func alpha(_ cutoffHz: CGFloat, _ dt: CGFloat) -> CGFloat {
            let tau = 1 / (2 * .pi * cutoffHz)
            return 1 / (1 + tau / dt)
        }
    }
}
