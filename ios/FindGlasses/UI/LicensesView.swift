import SwiftUI

/// 오픈소스 라이선스. Android `LicensesActivity.kt`.
/// 모델 가중치가 Ultralytics AGPL-3.0 이라 앱 전체 소스를 공개하고, 그 위치를 여기 둔다.
/// 원문은 공식 텍스트를 번들에 넣었다 (Resources/Licenses).
struct LicensesView: View {
    @Environment(\.dismiss) private var dismiss

    private struct Component: Identifiable {
        let id = UUID()
        let name, owner, license, url: String
        let textFile: String?
        var note: String? = nil
    }

    private static let sourceURL = "https://github.com/myaune/find-my-glasses"

    private let components = [
        Component(name: "YOLO-World v2 (yolov8s-worldv2)", owner: "Ultralytics", license: "AGPL-3.0",
                  url: "https://github.com/ultralytics/ultralytics", textFile: "license_agpl_3_0",
                  note: "Model weights. Original research: Tencent AILab CVC YOLO-World."),
        Component(name: "CLIP", owner: "OpenAI", license: "MIT", url: "https://github.com/openai/CLIP",
                  textFile: "license_mit_clip",
                  note: "Text embeddings are computed once at build time and baked into the model."),
        Component(name: "ONNX Runtime", owner: "Microsoft", license: "MIT",
                  url: "https://github.com/microsoft/onnxruntime", textFile: "license_mit_onnxruntime"),
        Component(name: "Google Mobile Ads SDK, User Messaging Platform", owner: "Google",
                  license: "Google Mobile Ads SDK Terms", url: "https://developers.google.com/admob/terms",
                  textFile: nil, note: "Proprietary. Not open source."),
    ]

    private let yellow = Color(red: 1, green: 214 / 255, blue: 0)

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 6) {
                    Text(L("licenses_intro")).font(.system(size: 17)).foregroundStyle(Color(white: 0.86))

                    Text(L("source_code")).font(.system(size: 20, weight: .bold)).foregroundStyle(yellow).padding(.top, 18)
                    Link(Self.sourceURL, destination: URL(string: Self.sourceURL)!)
                    LicenseText(file: "license_agpl_3_0")

                    Divider().padding(.vertical, 16)

                    ForEach(components) { c in
                        Text(c.name).font(.system(size: 19, weight: .bold)).padding(.top, 12)
                        Text("\(c.owner) · \(c.license)").font(.system(size: 15)).foregroundStyle(yellow)
                        if let note = c.note {
                            Text(note).font(.system(size: 14)).foregroundStyle(Color(white: 0.67))
                        }
                        Link(c.url, destination: URL(string: c.url)!).font(.system(size: 15))
                        if let f = c.textFile { LicenseText(file: f) }
                    }
                }
                .padding(20)
            }
            .navigationTitle(L("licenses"))
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button(L("settings_done")) { dismiss() } }
            }
        }
    }
}

/// 원문은 길어서 펼칠 때만 읽는다
private struct LicenseText: View {
    let file: String
    @State private var open = false
    @State private var text = ""

    var body: some View {
        VStack(alignment: .leading) {
            Button(L(open ? "hide_license" : "view_license")) {
                if text.isEmpty, let url = Bundle.main.url(forResource: file, withExtension: "txt") {
                    text = (try? String(contentsOf: url, encoding: .utf8)) ?? ""
                }
                open.toggle()
            }
            if open {
                Text(text)
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundStyle(Color(white: 0.8))
                    .padding(10)
                    .background(Color(white: 0.13))
            }
        }
    }
}
