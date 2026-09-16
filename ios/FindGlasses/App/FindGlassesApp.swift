import SwiftUI

@main
struct FindGlassesApp: App {
    @StateObject private var engine = FinderEngine()
    @Environment(\.scenePhase) private var phase

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(engine)
                .preferredColorScheme(.dark)
                .statusBarHidden(false)
        }
        .onChange(of: phase) { _, p in
            // 앱이 가려지면 카메라·자이로를 멈춘다 (배터리)
            switch p {
            case .active: engine.resume()
            case .background: engine.pause()
            default: break
            }
        }
    }
}
