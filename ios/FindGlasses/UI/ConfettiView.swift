import SwiftUI
import UIKit

/// 찾았을 때 양옆에서 터지는 폭죽. Android `ConfettiView.kt`. 외부 라이브러리 없이 파티클 수십 개.
final class ConfettiView: UIView {

    private struct P {
        var x, y, vx, vy, rot: CGFloat
        let vr, w, h: CGFloat
        let color: UIColor
        let circle: Bool
    }

    private var particles: [P] = []
    private var link: CADisplayLink?
    private var lastFrame: CFTimeInterval = 0
    private static let perSide = 70
    private static let colors: [UIColor] = [
        UIColor(red: 1, green: 214 / 255, blue: 0, alpha: 1),
        UIColor(red: 1, green: 138 / 255, blue: 0, alpha: 1),
        UIColor(red: 1, green: 45 / 255, blue: 85 / 255, alpha: 1),
        UIColor(red: 120 / 255, green: 200 / 255, blue: 1, alpha: 1),
        UIColor(red: 140 / 255, green: 230 / 255, blue: 140 / 255, alpha: 1),
        UIColor(red: 200 / 255, green: 140 / 255, blue: 1, alpha: 1),
    ]

    override init(frame: CGRect) {
        super.init(frame: frame)
        isOpaque = false
        backgroundColor = .clear
        isUserInteractionEnabled = false
    }

    required init?(coder: NSCoder) { fatalError() }

    /// 양옆 아래쪽에서 화면 중앙 위를 향해 한 번 터뜨린다
    func burst() {
        let w = bounds.width, h = bounds.height
        guard w > 0 else { return }
        particles.removeAll()
        let scale = w / 400  // Android 는 1080px 기준, 여기선 포인트 기준

        for fromLeft in [true, false] {
            let ox = fromLeft ? -8 * scale : w + 8 * scale
            let oy = h * 0.72
            for _ in 0..<Self.perSide {
                let base: Double = fromLeft ? -55 : -125
                let ang = (base + Double.random(in: -22...22)) * .pi / 180
                let speed = CGFloat(630 + Double.random(in: 0...555)) * scale
                particles.append(P(
                    x: ox, y: oy,
                    vx: CGFloat(cos(ang)) * speed, vy: CGFloat(sin(ang)) * speed,
                    rot: .random(in: 0...360), vr: .random(in: -360...360),
                    w: (5 + .random(in: 0...5)) * scale, h: (3 + .random(in: 0...4)) * scale,
                    color: Self.colors.randomElement()!, circle: Int.random(in: 0..<4) == 0))
            }
        }
        lastFrame = 0
        if link == nil {
            let l = CADisplayLink(target: self, selector: #selector(step))
            l.add(to: .main, forMode: .common)
            link = l
        }
    }

    @objc private func step(_ l: CADisplayLink) {
        let dt = lastFrame == 0 ? 0.016 : min(l.timestamp - lastFrame, 0.05)
        lastFrame = l.timestamp
        let g = 963 * (bounds.width / 400)
        let d = CGFloat(dt)
        for i in particles.indices.reversed() {
            particles[i].vy += g * d
            particles[i].vx *= 0.985
            particles[i].vy *= 0.985
            particles[i].x += particles[i].vx * d
            particles[i].y += particles[i].vy * d
            particles[i].rot += particles[i].vr * d
            if particles[i].y > bounds.height + 30 { particles.remove(at: i) }
        }
        if particles.isEmpty {
            link?.invalidate()
            link = nil
        }
        setNeedsDisplay()
    }

    override func draw(_ rect: CGRect) {
        guard let ctx = UIGraphicsGetCurrentContext() else { return }
        for p in particles {
            ctx.saveGState()
            ctx.translateBy(x: p.x, y: p.y)
            ctx.rotate(by: p.rot * .pi / 180)
            ctx.setFillColor(p.color.cgColor)
            if p.circle {
                let r = p.w * 0.4
                ctx.fillEllipse(in: CGRect(x: -r, y: -r, width: r * 2, height: r * 2))
            } else {
                ctx.fill(CGRect(x: -p.w / 2, y: -p.h / 2, width: p.w, height: p.h))
            }
            ctx.restoreGState()
        }
    }
}

struct ConfettiRepresentable: UIViewRepresentable {
    let view: ConfettiView
    func makeUIView(context: Context) -> ConfettiView { view }
    func updateUIView(_ uiView: ConfettiView, context: Context) {}
}
