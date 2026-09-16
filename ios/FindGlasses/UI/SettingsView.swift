import SwiftUI

/// 설정: 음성 / 진동 / 언어 / 광고 없애기 / 개인정보. Android `dialog_settings.xml` + `MainActivity.showSettings`.
///
/// 언어: iOS 는 앱별 언어를 시스템 설정(설정 → 앱 → 언어)에서 바꾸는 게 표준이다.
/// 지금 쓰는 언어 이름을 보여주고, 누르면 이 앱의 설정 화면을 연다.
struct SettingsView: View {
    @EnvironmentObject var engine: FinderEngine
    @Environment(\.dismiss) private var dismiss

    @State private var voice = true
    @State private var vibration = true
    @State private var price: String?
    @State private var bought = false
    @State private var toast: String?

    private static let privacyPolicyURL = URL(string: "https://myaune.github.io/find-my-glasses/privacy/")!
    private let yellow = Color(red: 1, green: 214 / 255, blue: 0)

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                Toggle(L("settings_voice"), isOn: $voice)
                    .font(.system(size: 18))
                    .frame(height: 52)
                    .onChange(of: voice) { _, on in
                        engine.feedback.voiceEnabled = on
                        UserDefaults.standard.set(on, forKey: FinderEngine.prefVoice)
                    }
                Toggle(L("settings_vibration"), isOn: $vibration)
                    .font(.system(size: 18))
                    .frame(height: 52)
                    .onChange(of: vibration) { _, on in
                        engine.feedback.vibrationEnabled = on
                        UserDefaults.standard.set(on, forKey: FinderEngine.prefVibration)
                    }

                // [언어]            [한국어 ▸]
                Button {
                    if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
                } label: {
                    HStack {
                        Text(L("settings_language")).font(.system(size: 18)).foregroundStyle(.white)
                        Spacer()
                        Text(currentLanguageName)
                            .font(.system(size: 15, weight: .bold))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 14)
                            .frame(height: 40)
                            .overlay(Capsule().stroke(Color.white.opacity(0.66), lineWidth: 1.5))
                    }
                    .frame(height: 52)
                }

                supportCard.padding(.top, 14)

                HStack {
                    Link(L("privacy_policy"), destination: Self.privacyPolicyURL)
                    if engine.consent.privacyOptionsRequired {
                        Button(L("privacy_options")) {
                            if let vc = UIApplication.shared.topViewController {
                                engine.consent.showPrivacyOptions(from: vc)
                            }
                        }
                    }
                }
                .font(.system(size: 13))
                .padding(.top, 6)

                Spacer()
            }
            .padding(.horizontal, 24)
            .navigationTitle(L("settings"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button(L("settings_done")) { dismiss() } }
            }
            .overlay(alignment: .bottom) {
                if let toast {
                    Text(toast)
                        .padding(.horizontal, 16).padding(.vertical, 10)
                        .background(Capsule().fill(Color(white: 0.2)))
                        .padding(.bottom, 24)
                        .transition(.opacity)
                }
            }
        }
        .presentationDetents([.large])
        .onAppear {
            voice = engine.feedback.voiceEnabled
            vibration = engine.feedback.vibrationEnabled
            bought = engine.purchases.adFree || !engine.ads.enabled
        }
        .task { price = await engine.purchases.removeAdsPrice() }
    }

    /// 앱이 실제로 쓰는 언어를 그 언어로 적는다 (예: 한국어, English)
    private var currentLanguageName: String {
        let id = Bundle.main.preferredLocalizations.first ?? "en"
        return Locale(identifier: id).localizedString(forIdentifier: id)?.capitalized ?? id
    }

    /// 광고 없애기 (IAP). 이미 샀으면 버튼 대신 고맙다는 말만 남긴다.
    private var supportCard: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(L(bought ? "support_thanks_title" : "support_title"))
                .font(.system(size: 17, weight: .bold))
                .foregroundStyle(yellow)
            Text(L(bought ? "support_thanks_body" : "support_body"))
                .font(.system(size: 14))
            if !bought {
                Button {
                    Task { handle(await engine.purchases.buyRemoveAds()) }
                } label: {
                    Text(price.map { String(format: L("support_buy"), $0) } ?? L("support_buy_noprice"))
                        .font(.system(size: 16))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                }
                .buttonStyle(.borderedProminent)
                .padding(.top, 8)

                Button(L("restore_purchases")) {
                    Task { handle(await engine.purchases.restore()) }
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 4)
            }
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 16).fill(yellow.opacity(0.12)))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(yellow.opacity(0.4), lineWidth: 1))
    }

    private func handle(_ r: PurchaseResult) {
        switch r {
        case .purchased, .restored:
            engine.ads.disable()
            bought = true
            show(L("support_thanks_title"))
        case .nothingToRestore: show(L("purchases_nothing"))
        case .unavailable: show(L("purchases_unavailable"))
        case .cancelled: break
        }
    }

    private func show(_ text: String) {
        withAnimation { toast = text }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { withAnimation { toast = nil } }
    }
}
