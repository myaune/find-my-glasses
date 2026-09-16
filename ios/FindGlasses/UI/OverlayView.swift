import SwiftUI
import UIKit

/// 위치 표시. Android `OverlayView.kt` 의 이식.
///
/// 표시는 하나만 한다. 화면 밖으로 나가면 가장자리 큰 화살표로 방향을 유지한다
/// (추론이 1초 안팎이라 이게 없으면 정보가 증발한다).
/// 어느 스레드에서든 [setTarget] 을 부를 수 있고, 그리기는 화면 주사율로 한다.
final class OverlayView: UIView {

    // 백그라운드 스레드에서 쓰고 메인에서 읽는다. 락으로만 접근한다.
    nonisolated(unsafe) private let lock = NSLock()
    nonisolated(unsafe) private var target: CGRect?
    nonisolated(unsafe) private var confidence: Confidence = .low
    nonisolated(unsafe) private var message = ""
    nonisolated(unsafe) private var frameW: CGFloat = 0
    nonisolated(unsafe) private var frameH: CGFloat = 0
    nonisolated(unsafe) private var needsClear = false

    private let smooth = SmoothBox()
    private var link: CADisplayLink?

    override init(frame: CGRect) {
        super.init(frame: frame)
        isOpaque = false
        backgroundColor = .clear
        isUserInteractionEnabled = false
        contentMode = .redraw
    }

    required init?(coder: NSCoder) { fatalError() }

    override func didMoveToWindow() {
        super.didMoveToWindow()
        link?.invalidate()
        link = nil
        if window != nil {
            let l = CADisplayLink(target: self, selector: #selector(tick))
            l.add(to: .main, forMode: .common)
            link = l
        }
    }

    @objc private func tick() {
        lock.lock(); let has = target != nil; lock.unlock()
        // 표시할 게 있으면 펄스·보간을 위해 계속 다시 그린다
        if has || needsClear { setNeedsDisplay() }
    }

    /// - Parameters:
    ///   - box: 똑바로 세운 프레임 좌표. nil 이면 지운다.
    nonisolated func setTarget(_ box: CGRect?, confidence: Confidence, message: String) {
        lock.lock()
        if box == nil && target != nil { needsClear = true }
        target = box
        self.confidence = confidence
        self.message = message
        lock.unlock()
    }

    nonisolated func setFrameSize(width: Int, height: Int) {
        lock.lock()
        frameW = CGFloat(width)
        frameH = CGFloat(height)
        lock.unlock()
    }

    override func draw(_ rect: CGRect) {
        lock.lock()
        let t = target, conf = confidence, msg = message, fw = frameW, fh = frameH
        needsClear = false
        lock.unlock()

        guard let t, fw > 0, fh > 0, let ctx = UIGraphicsGetCurrentContext() else {
            smooth.reset()
            return
        }

        // 프리뷰는 aspectFill. 같은 방식으로 맞춘다.
        let scale = max(bounds.width / fw, bounds.height / fh)
        let dx = (bounds.width - fw * scale) / 2
        let dy = (bounds.height - fh * scale) / 2
        let mapped = CGRect(x: t.minX * scale + dx, y: t.minY * scale + dy,
                            width: t.width * scale, height: t.height * scale)
        let box = smooth.update(mapped, viewWidth: bounds.width, now: CACurrentMediaTime())

        let phase = CACurrentMediaTime().truncatingRemainder(dividingBy: conf.pulse) / conf.pulse
        let pulse = CGFloat(0.5 + 0.5 * sin(phase * 2 * .pi))

        let onScreen = box.maxX > 0 && box.minX < bounds.width && box.maxY > 0 && box.minY < bounds.height
        if onScreen {
            drawOnScreen(ctx, box, conf, msg, pulse)
        } else {
            drawEdgeArrow(ctx, box, conf, msg, pulse)
        }
    }

    private func drawOnScreen(_ ctx: CGContext, _ box: CGRect, _ conf: Confidence, _ msg: String, _ pulse: CGFloat) {
        let W = bounds.width
        let lw = W * 0.012 * (0.75 + 0.5 * pulse)
        let alpha = min(1, (170 + 85 * pulse) / 255)

        // 너무 작으면 안경을 못 보는 사용자가 알아볼 수 없다. 최소 크기를 준다.
        let minSide = W * 0.18
        var r = box
        if r.width < minSide { r = r.insetBy(dx: (r.width - minSide) / 2, dy: 0) }
        if r.height < minSide { r = r.insetBy(dx: 0, dy: (r.height - minSide) / 2) }

        let radius = W * 0.03
        ctx.setStrokeColor(conf.color.withAlphaComponent(alpha).cgColor)
        ctx.setLineWidth(lw)
        ctx.addPath(UIBezierPath(roundedRect: r, cornerRadius: radius).cgPath)
        ctx.strokePath()

        // 네모를 가리키는 화살표 네 개. 펄스에 맞춰 안쪽으로 밀려온다.
        ctx.setFillColor(conf.color.cgColor)
        let gap = W * (0.055 - 0.018 * pulse)
        let size = W * 0.05
        triangle(ctx, r.midX, r.minY - gap, size, 90)
        triangle(ctx, r.midX, r.maxY + gap, size, 270)
        triangle(ctx, r.minX - gap, r.midY, size, 0)
        triangle(ctx, r.maxX + gap, r.midY, size, 180)

        if !msg.isEmpty {
            let fontSize = W * 0.055
            let y = max(r.minY - gap - size - W * 0.03, fontSize * 1.4)
            drawMessage(msg, centerX: W / 2, baselineY: y, fontSize: fontSize)
        }
    }

    private func drawEdgeArrow(_ ctx: CGContext, _ box: CGRect, _ conf: Confidence, _ msg: String, _ pulse: CGFloat) {
        let W = bounds.width
        let cx = W / 2, cy = bounds.height / 2
        let ang = atan2(box.midY - cy, box.midX - cx)
        let margin = W * 0.14
        let px = cx + (cx - margin) * cos(ang)
        let py = cy + (cy - margin) * sin(ang)

        let alpha = min(1, (170 + 85 * pulse) / 255)
        ctx.setFillColor(conf.color.withAlphaComponent(alpha).cgColor)
        triangle(ctx, px, py, W * 0.11 * (0.9 + 0.2 * pulse), ang * 180 / .pi + 180)

        if !msg.isEmpty {
            let fontSize = W * 0.055
            drawMessage(msg, centerX: cx, baselineY: cy + fontSize * 0.4, fontSize: fontSize)
        }
        // 거리 감각을 주는 작은 원 (멀수록 흐리게)
        let dist = hypot(box.midX - cx, box.midY - cy)
        let a = (60 + 120 * (1 - min(dist / (W * 2), 1))) / 255
        ctx.setStrokeColor(conf.color.withAlphaComponent(a).cgColor)
        ctx.setLineWidth(W * 0.006)
        ctx.strokeEllipse(in: CGRect(x: cx - W * 0.05, y: cy - W * 0.05, width: W * 0.1, height: W * 0.1))
    }

    /// headingDeg = 화살표가 가리키는 방향 (0 = 오른쪽, 시계방향)
    private func triangle(_ ctx: CGContext, _ cx: CGFloat, _ cy: CGFloat, _ size: CGFloat, _ headingDeg: CGFloat) {
        let a = headingDeg * .pi / 180
        let tip = CGPoint(x: cx + size * cos(a), y: cy + size * sin(a))
        let back = a + .pi
        let bx = cx + size * 0.5 * cos(back)
        let by = cy + size * 0.5 * sin(back)
        let perp = a + .pi / 2
        let ox = size * 0.55 * cos(perp)
        let oy = size * 0.55 * sin(perp)
        ctx.move(to: tip)
        ctx.addLine(to: CGPoint(x: bx + ox, y: by + oy))
        ctx.addLine(to: CGPoint(x: bx - ox, y: by - oy))
        ctx.closePath()
        ctx.fillPath()
    }

    private func drawMessage(_ text: String, centerX: CGFloat, baselineY: CGFloat, fontSize: CGFloat) {
        let shadow = NSShadow()
        shadow.shadowColor = UIColor.black
        shadow.shadowBlurRadius = 10
        shadow.shadowOffset = CGSize(width: 0, height: 2)
        let attrs: [NSAttributedString.Key: Any] = [
            .font: UIFont.systemFont(ofSize: fontSize, weight: .bold),
            .foregroundColor: UIColor.white,
            .shadow: shadow,
        ]
        let s = NSAttributedString(string: text, attributes: attrs)
        let size = s.size()
        s.draw(at: CGPoint(x: centerX - size.width / 2, y: baselineY - size.height * 0.8))
    }
}

struct OverlayRepresentable: UIViewRepresentable {
    let view: OverlayView
    func makeUIView(context: Context) -> OverlayView { view }
    func updateUIView(_ uiView: OverlayView, context: Context) {}
}
