import SwiftUI

/// 제품 화면. Android `activity_main.xml` 과 같은 배치.
///   전체 라이브 프리뷰 + 위치 표시 + 상단 버튼 줄 + 안내 문구 + 하단 배너
struct ContentView: View {
    @EnvironmentObject var engine: FinderEngine
    @State private var showSettings = false
    @State private var showTargetPicker = false
    @State private var showLicenses = false

    var body: some View {
        ZStack {
            VStack(spacing: 0) {
                ZStack {
                    CameraPreviewRepresentable(engine: engine)
                    OverlayRepresentable(view: engine.overlay)

                    VStack(spacing: 0) {
                        topBar
                        if let key = engine.hintKey {
                            Text(L(key))
                                .font(.system(size: 20, weight: .bold))
                                .foregroundStyle(.white)
                                .shadow(color: .black, radius: 8)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 16)
                                .padding(.top, 14)
                        }
                        Spacer()
                        bottomControls
                    }

                    if engine.cameraDenied { cameraDeniedNotice }
                }
                .clipped()

                if engine.ads.enabled {
                    BannerAdView()
                        .frame(height: 50)
                        .frame(maxWidth: .infinity)
                        .background(Color(white: 0.06))
                }
            }
            .background(Color.black)

            if engine.celebrating { CelebrationView() }

            if engine.tutorialOpen {
                TutorialView(onFinish: { engine.closeTutorial() },
                             onLicenses: { showLicenses = true })
                    .transition(.opacity)
            }

            if engine.loading {
                ZStack {
                    Color.black.opacity(0.7).ignoresSafeArea()
                    VStack(spacing: 14) {
                        ProgressView().tint(.white)
                        Text(L("preparing")).foregroundStyle(.white)
                    }
                }
            }
        }
        .task { await engine.start() }
        .sheet(isPresented: $showSettings) { SettingsView() }
        .sheet(isPresented: $showTargetPicker) { TargetPickerView() }
        .sheet(isPresented: $showLicenses) { LicensesView() }
    }

    private var topBar: some View {
        HStack(spacing: 6) {
            CircleButton(label: "?") { engine.openTutorial() }
                .accessibilityLabel(L("tut_help"))

            Menu {
                ForEach(ModelCatalog.qualities, id: \.self) { q in
                    Button("\(L(q.labelKey)) · \(q.size)px") { engine.setQuality(q.size) }
                }
            } label: {
                let current = ModelCatalog.qualities.first { $0.size == engine.inputSize }
                Text("\(L(current?.labelKey ?? "quality_normal")) · \(engine.inputSize)px ▾")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 14)
                    .frame(height: 44)
                    .background(Capsule().fill(Color.black.opacity(0.4)))
                    .overlay(Capsule().stroke(Color.white.opacity(0.66), lineWidth: 1.5))
            }

            Spacer()

            CircleButton(label: "⚙") { showSettings = true }
                .accessibilityLabel(L("settings"))
        }
        .padding(.horizontal, 10)
        .padding(.top, 10)
    }

    private var bottomControls: some View {
        VStack(spacing: 8) {
            if engine.showFoundButton {
                Button {
                    engine.onFound()
                } label: {
                    Text(L("found_it"))
                        .font(.system(size: 20, weight: .bold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                }
                .buttonStyle(.borderedProminent)
                .padding(.horizontal, 32)
            }

            HStack {
                Spacer()
                // 다른 물건 찾기 (테스트 안 된 부가 기능). 구석에 작게.
                Button {
                    showTargetPicker = true
                } label: {
                    Text(engine.target == .glasses ? L("target_other")
                         : "\(engine.target.emoji) \(L(engine.target.labelKey))")
                        .font(.system(size: 13))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Capsule().fill(Color.black.opacity(0.4)))
                        .overlay(Capsule().stroke(Color.white.opacity(0.66), lineWidth: 1.5))
                        .opacity(engine.target == .glasses ? 0.55 : 1)
                }
            }
            .padding(8)
        }
    }

    private var cameraDeniedNotice: some View {
        VStack(spacing: 12) {
            Text("📷").font(.system(size: 48))
            Button("Settings") {
                if let url = URL(string: UIApplication.openSettingsURLString) {
                    UIApplication.shared.open(url)
                }
            }
            .buttonStyle(.borderedProminent)
        }
    }
}

struct CircleButton: View {
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.system(size: 22, weight: .bold))
                .foregroundStyle(.white)
                .frame(width: 44, height: 44)
                .background(Circle().fill(Color.black.opacity(0.4)))
                .overlay(Circle().stroke(Color.white.opacity(0.66), lineWidth: 2))
        }
    }
}

struct CameraPreviewRepresentable: UIViewRepresentable {
    let engine: FinderEngine
    func makeUIView(context: Context) -> CameraPreviewView { CameraPreviewView(session: engine.camera.session) }
    func updateUIView(_ uiView: CameraPreviewView, context: Context) {}
}

/// 찾았어요! — 찾은 순간의 사진을 가운데, 양옆 폭죽
struct CelebrationView: View {
    @EnvironmentObject var engine: FinderEngine
    @State private var appeared = false

    var body: some View {
        ZStack {
            Color.black.opacity(0.8).ignoresSafeArea()
            VStack(spacing: 22) {
                Text(L("celebrate"))
                    .font(.system(size: 40, weight: .heavy))
                    .foregroundStyle(Color(red: 1, green: 214 / 255, blue: 0))
                if let img = engine.snapshot {
                    Image(uiImage: img)
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: 300, maxHeight: 300)
                        .clipShape(RoundedRectangle(cornerRadius: 18))
                        .overlay(RoundedRectangle(cornerRadius: 18)
                            .stroke(Color(red: 1, green: 214 / 255, blue: 0), lineWidth: 4))
                }
            }
            ConfettiRepresentable(view: engine.confetti).ignoresSafeArea()
        }
        .opacity(appeared ? 1 : 0)
        .onAppear { withAnimation(.easeOut(duration: 0.22)) { appeared = true } }
    }
}
