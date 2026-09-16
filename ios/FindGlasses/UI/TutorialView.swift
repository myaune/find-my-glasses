import SwiftUI

/// 첫 실행 튜토리얼. 게임 튜토리얼처럼 한 장씩 넘긴다. Android `Tutorial.kt` + `TutorialArtView.kt`.
///   1 천천히 둘러보기 — 폰이 좌우로 훑는 그림
///   2 찾으면 이렇게 표시 — 실제 화면과 같은 OverlayView 로 노랑→연두→초록
///   3 대비가 강하면 잘 찾음 — 단색 면 ✓ / 복잡한 면은 가까이
struct TutorialView: View {
    let onFinish: () -> Void
    let onLicenses: () -> Void

    @State private var page = 0

    private let pages: [(TutorialArt.Mode, String, String)] = [
        (.sweep, "tut_step1_title", "tut_step1_body"),
        (.glasses, "tut_step2_title", "tut_step2_body"),
        (.contrast, "tut_step3_title", "tut_step3_body"),
    ]

    private let yellow = Color(red: 1, green: 214 / 255, blue: 0)

    var body: some View {
        ZStack {
            Color(white: 0.07).ignoresSafeArea()
            VStack(spacing: 0) {
                HStack {
                    Spacer()
                    Button(L("tut_skip"), action: onFinish)
                        .font(.system(size: 17))
                        .foregroundStyle(Color(white: 0.62))
                        .padding(18)
                }

                TabView(selection: $page) {
                    ForEach(pages.indices, id: \.self) { i in
                        let p = pages[i]
                        VStack(spacing: 0) {
                            ZStack {
                                RoundedRectangle(cornerRadius: 20).fill(Color(red: 34 / 255, green: 34 / 255, blue: 38 / 255))
                                TutorialArt(mode: p.0)
                                if p.0 == .glasses { TutorialOverlayDemo() }
                            }
                            .clipShape(RoundedRectangle(cornerRadius: 20))
                            .padding(.bottom, 20)

                            Text(L(p.1))
                                .font(.system(size: 30, weight: .bold))
                                .foregroundStyle(yellow)
                                .multilineTextAlignment(.center)
                            Text(L(p.2))
                                .font(.system(size: 20))
                                .foregroundStyle(Color(white: 0.9))
                                .lineSpacing(5)
                                .multilineTextAlignment(.center)
                                .padding(.top, 12)
                                .padding(.bottom, 8)
                        }
                        .padding(.horizontal, 28)
                        .tag(i)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))

                // 페이지 점
                HStack(spacing: 12) {
                    ForEach(pages.indices, id: \.self) { i in
                        Circle().fill(i == page ? yellow : Color(white: 0.35)).frame(width: 10, height: 10)
                    }
                }
                .padding(.top, 8)

                Button {
                    if page < pages.count - 1 { withAnimation { page += 1 } } else { onFinish() }
                } label: {
                    Text(L(page == pages.count - 1 ? "tut_start" : "tut_next"))
                        .font(.system(size: 22, weight: .bold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 18)
                }
                .buttonStyle(.borderedProminent)
                .padding(.horizontal, 28)
                .padding(.top, 18)

                // 오픈소스 라이선스 (AGPL-3.0 의무 포함)
                Button(L("licenses"), action: onLicenses)
                    .font(.system(size: 14))
                    .foregroundStyle(Color(white: 0.62))
                    .padding(14)
            }
        }
    }
}

/// 튜토리얼 그림. 이미지 파일 없이 직접 그린다. Android `TutorialArtView.kt`.
struct TutorialArt: View {
    enum Mode { case sweep, glasses, contrast }
    let mode: Mode

    /// CONTRAST 무늬 — 매 프레임 바뀌면 어지러우니 한 번만 만든다
    @State private var noise: [[CGFloat]] = (0..<90).map { _ in (0..<4).map { _ in .random(in: 0...1) } }

    var body: some View {
        switch mode {
        case .sweep:
            TimelineView(.animation) { tl in
                Canvas { ctx, size in drawSweep(&ctx, size, tl.date.timeIntervalSinceReferenceDate) }
            }
        case .glasses:
            Canvas { ctx, size in
                drawGlasses(&ctx, CGPoint(x: size.width / 2, y: size.height * 0.58), size.width * 0.26,
                            frame: Color(white: 0.16), lens: Color(white: 0.92))
            }
        case .contrast:
            Canvas { ctx, size in drawContrast(&ctx, size) }
        }
    }

    private func drawSweep(_ ctx: inout GraphicsContext, _ size: CGSize, _ time: Double) {
        let w = size.width, h = size.height
        ctx.fill(Path(CGRect(x: 0, y: h * 0.72, width: w, height: h * 0.28)), with: .color(Color(red: 48 / 255, green: 48 / 255, blue: 52 / 255)))
        drawGlasses(&ctx, CGPoint(x: w * 0.66, y: h * 0.84), w * 0.12, frame: Color(white: 0.24), lens: Color(white: 0.86))

        // 폰이 좌우로 천천히 흔들린다 (4초 주기)
        let t = time.truncatingRemainder(dividingBy: 4) / 4
        let s = CGFloat(sin(t * 2 * .pi))
        let cx = w / 2 + s * w * 0.22, cy = h * 0.34
        let pw = w * 0.13, ph = pw * 1.9

        // 지나간 자리 잔상
        for i in 1...4 {
            let ss = CGFloat(sin((t - Double(i) * 0.025) * 2 * .pi))
            let gx = w / 2 + ss * w * 0.22
            let r = CGRect(x: gx - pw / 2, y: cy - ph / 2, width: pw, height: ph)
            ctx.stroke(Path(roundedRect: r, cornerRadius: pw * 0.18),
                       with: .color(Color(red: 1, green: 214 / 255, blue: 0).opacity(Double(60 - i * 12) / 255)),
                       lineWidth: w * 0.008)
        }

        // 카메라가 비추는 영역
        var cone = Path()
        cone.move(to: CGPoint(x: cx, y: cy + ph / 2))
        cone.addLine(to: CGPoint(x: cx - w * 0.2, y: h * 0.72))
        cone.addLine(to: CGPoint(x: cx + w * 0.2, y: h * 0.72))
        cone.closeSubpath()
        ctx.fill(cone, with: .color(Color(red: 1, green: 214 / 255, blue: 0).opacity(46.0 / 255)))

        // 폰 본체
        let body = CGRect(x: cx - pw / 2, y: cy - ph / 2, width: pw, height: ph)
        ctx.fill(Path(roundedRect: body, cornerRadius: pw * 0.18), with: .color(Color(white: 0.98)))
        ctx.fill(Path(roundedRect: body.insetBy(dx: pw * 0.08, dy: pw * 0.1), cornerRadius: pw * 0.1),
                 with: .color(Color(red: 30 / 255, green: 30 / 255, blue: 34 / 255)))

        // 좌우 화살표
        let ay = h * 0.1
        let yellow = GraphicsContext.Shading.color(Color(red: 1, green: 214 / 255, blue: 0))
        var arrow = Path()
        arrow.move(to: CGPoint(x: w * 0.3, y: ay)); arrow.addLine(to: CGPoint(x: w * 0.7, y: ay))
        arrowHead(&arrow, w * 0.3, ay, -1, w * 0.03)
        arrowHead(&arrow, w * 0.7, ay, 1, w * 0.03)
        ctx.stroke(arrow, with: yellow, style: StrokeStyle(lineWidth: w * 0.012, lineCap: .round))
    }

    private func drawContrast(_ ctx: inout GraphicsContext, _ size: CGSize) {
        let w = size.width, h = size.height
        let gap = w * 0.04
        let pw = (w - gap * 3) / 2
        let top = h * 0.08, bottom = h * 0.92

        // 왼쪽 — 단색 면, 안경이 또렷하다
        let l = CGRect(x: gap, y: top, width: pw, height: bottom - top)
        ctx.fill(Path(roundedRect: l, cornerRadius: w * 0.03), with: .color(Color(red: 236 / 255, green: 230 / 255, blue: 214 / 255)))
        drawGlasses(&ctx, CGPoint(x: l.midX, y: l.midY - h * 0.04), pw * 0.34, frame: Color(white: 0.1), lens: nil)
        badge(&ctx, CGPoint(x: l.midX, y: bottom - h * 0.13), w * 0.055, ok: true)

        // 오른쪽 — 복잡한 무늬, 안경이 묻힌다
        let r = CGRect(x: gap * 2 + pw, y: top, width: pw, height: bottom - top)
        var inner = ctx
        inner.clip(to: Path(r))
        inner.fill(Path(r), with: .color(Color(red: 120 / 255, green: 100 / 255, blue: 150 / 255)))
        for n in noise {
            let c = Color(red: (80 + n[2] * 150) / 255, green: (70 + n[3] * 120) / 255, blue: 140 / 255)
            let rad = w * (0.012 + n[2] * 0.03)
            inner.fill(Path(ellipseIn: CGRect(x: r.minX + n[0] * r.width - rad, y: r.minY + n[1] * r.height - rad,
                                              width: rad * 2, height: rad * 2)), with: .color(c))
        }
        drawGlasses(&inner, CGPoint(x: r.midX, y: r.midY - h * 0.04), pw * 0.34,
                    frame: Color(red: 110 / 255, green: 90 / 255, blue: 140 / 255), lens: nil)
        badge(&ctx, CGPoint(x: r.midX, y: bottom - h * 0.13), w * 0.055, ok: false)
    }

    /// ✓ 또는 "가까이" (가운데로 모이는 화살표)
    private func badge(_ ctx: inout GraphicsContext, _ c: CGPoint, _ rad: CGFloat, ok: Bool) {
        ctx.fill(Path(ellipseIn: CGRect(x: c.x - rad, y: c.y - rad, width: rad * 2, height: rad * 2)),
                 with: .color(ok ? Color(red: 46 / 255, green: 180 / 255, blue: 90 / 255) : Color(red: 1, green: 138 / 255, blue: 0)))
        var p = Path()
        if ok {
            p.move(to: CGPoint(x: c.x - rad * 0.45, y: c.y))
            p.addLine(to: CGPoint(x: c.x - rad * 0.1, y: c.y + rad * 0.35))
            p.addLine(to: CGPoint(x: c.x + rad * 0.5, y: c.y - rad * 0.35))
        } else {
            p.move(to: CGPoint(x: c.x - rad * 0.6, y: c.y)); p.addLine(to: CGPoint(x: c.x - rad * 0.15, y: c.y))
            p.move(to: CGPoint(x: c.x + rad * 0.6, y: c.y)); p.addLine(to: CGPoint(x: c.x + rad * 0.15, y: c.y))
            arrowHead(&p, c.x - rad * 0.15, c.y, 1, rad * 0.25)
            arrowHead(&p, c.x + rad * 0.15, c.y, -1, rad * 0.25)
        }
        ctx.stroke(p, with: .color(.white), style: StrokeStyle(lineWidth: rad * 0.22, lineCap: .round, lineJoin: .round))
    }

    private func arrowHead(_ p: inout Path, _ x: CGFloat, _ y: CGFloat, _ dir: CGFloat, _ size: CGFloat) {
        p.move(to: CGPoint(x: x, y: y)); p.addLine(to: CGPoint(x: x - dir * size, y: y - size * 0.7))
        p.move(to: CGPoint(x: x, y: y)); p.addLine(to: CGPoint(x: x - dir * size, y: y + size * 0.7))
    }

    /// 안경 아이콘. lensW = 한쪽 렌즈 폭
    private func drawGlasses(_ ctx: inout GraphicsContext, _ c: CGPoint, _ lensW: CGFloat, frame: Color, lens: Color?) {
        let lensH = lensW * 0.72
        let bridge = lensW * 0.34
        let left = CGRect(x: c.x - bridge / 2 - lensW, y: c.y - lensH / 2, width: lensW, height: lensH)
        let right = CGRect(x: c.x + bridge / 2, y: c.y - lensH / 2, width: lensW, height: lensH)
        let corner = lensW * 0.3

        if let lens {
            ctx.fill(Path(roundedRect: left, cornerRadius: corner), with: .color(lens.opacity(70.0 / 255)))
            ctx.fill(Path(roundedRect: right, cornerRadius: corner), with: .color(lens.opacity(70.0 / 255)))
        }
        var p = Path(roundedRect: left, cornerRadius: corner)
        p.addPath(Path(roundedRect: right, cornerRadius: corner))
        p.move(to: CGPoint(x: left.maxX, y: c.y - lensH * 0.12))
        p.addQuadCurve(to: CGPoint(x: right.minX, y: c.y - lensH * 0.12), control: CGPoint(x: c.x, y: c.y - lensH * 0.38))
        p.move(to: CGPoint(x: left.minX, y: c.y - lensH * 0.25))
        p.addLine(to: CGPoint(x: left.minX - lensW * 0.35, y: c.y - lensH * 0.05))
        p.move(to: CGPoint(x: right.maxX, y: c.y - lensH * 0.25))
        p.addLine(to: CGPoint(x: right.maxX + lensW * 0.35, y: c.y - lensH * 0.05))
        ctx.stroke(p, with: .color(frame), style: StrokeStyle(lineWidth: lensW * 0.11, lineCap: .round, lineJoin: .round))
    }
}

/// 2장 그림: 실제 화면과 같은 OverlayView 로 신뢰도가 올라가며 색이 바뀌는 것을 보여준다
struct TutorialOverlayDemo: View {
    @State private var overlay = OverlayView()
    @State private var step = 0
    private let timer = Timer.publish(every: 1.5, on: .main, in: .common).autoconnect()

    var body: some View {
        GeometryReader { geo in
            OverlayRepresentable(view: overlay)
                .onAppear { apply(geo.size) }
                .onReceive(timer) { _ in
                    step += 1
                    apply(geo.size)
                }
        }
    }

    private func apply(_ size: CGSize) {
        guard size.width > 0 else { return }
        overlay.setFrameSize(width: Int(size.width), height: Int(size.height))
        let conf = Confidence.allCases[step % Confidence.allCases.count]
        // TutorialArt 가 안경을 그리는 자리와 맞춘다
        let bw = size.width * 0.66, bh = size.width * 0.26, cy = size.height * 0.58
        overlay.setTarget(CGRect(x: size.width / 2 - bw / 2, y: cy - bh / 2, width: bw, height: bh),
                          confidence: conf, message: L(conf.messageKey))
    }
}
