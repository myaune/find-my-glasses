import GoogleMobileAds
import SwiftUI
import UIKit

/// 광고. Android `Ads.kt`.
///   하단 배너 고정
///   [찾았다!] → 전면 광고 (태스크 완료 직후, 성공했을 때만)
///
/// 광고 ID 는 Info.plist 의 AdmobBannerId / AdmobInterstitialId 에서 읽는다.
/// 값은 xcconfig 가 넣는다: Debug = 구글 테스트 ID, Release = Config/Secrets.xcconfig (git 제외).
@MainActor
final class Ads: NSObject, FullScreenContentDelegate {

    /// 광고 제거를 사면 false
    var enabled = true
    private(set) var started = false

    private var interstitial: InterstitialAd?
    private var onDismiss: (() -> Void)?

    static var bannerId: String { Bundle.main.object(forInfoDictionaryKey: "AdmobBannerId") as? String ?? "" }
    static var interstitialId: String { Bundle.main.object(forInfoDictionaryKey: "AdmobInterstitialId") as? String ?? "" }

    func start() {
        guard enabled, !started else { return }
        started = true
        MobileAds.shared.start(completionHandler: nil)
        preloadInterstitial()
    }

    func preloadInterstitial() {
        guard enabled, started, interstitial == nil else { return }
        InterstitialAd.load(with: Self.interstitialId, request: Request()) { [weak self] ad, error in
            if let error { NSLog("[Ads] 전면 광고 실패: \(error)") }
            self?.interstitial = ad
        }
    }

    /// 태스크 완료 직후에만 부른다. - Parameter onDone: 광고가 닫히거나 없을 때
    func showInterstitial(from vc: UIViewController, onDone: @escaping () -> Void) {
        guard enabled, let ad = interstitial else {
            onDone()
            preloadInterstitial()
            return
        }
        onDismiss = onDone
        ad.fullScreenContentDelegate = self
        ad.present(from: vc)
    }

    /// 광고 제거를 샀을 때
    func disable() {
        enabled = false
        interstitial = nil
    }

    nonisolated func adDidDismissFullScreenContent(_ ad: FullScreenAd) {
        Task { @MainActor in self.finish() }
    }

    nonisolated func ad(_ ad: FullScreenAd, didFailToPresentFullScreenContentWithError error: Error) {
        Task { @MainActor in self.finish() }
    }

    private func finish() {
        interstitial = nil
        preloadInterstitial()
        let done = onDismiss
        onDismiss = nil
        done?()
    }
}

/// 하단 배너
struct BannerAdView: UIViewRepresentable {
    func makeUIView(context: Context) -> BannerView {
        let v = BannerView(adSize: AdSizeBanner)
        v.adUnitID = Ads.bannerId
        v.rootViewController = UIApplication.shared.topViewController
        v.load(Request())
        return v
    }

    func updateUIView(_ uiView: BannerView, context: Context) {}
}

extension UIApplication {
    /// 광고·동의 창을 띄울 뷰컨트롤러
    var topViewController: UIViewController? {
        let scene = connectedScenes.first { $0.activationState == .foregroundActive } as? UIWindowScene
        var vc = scene?.windows.first { $0.isKeyWindow }?.rootViewController
        while let p = vc?.presentedViewController { vc = p }
        return vc
    }
}
