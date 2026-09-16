import UIKit
import UserMessagingPlatform

/// 광고 동의 (Google UMP). Android `Consent.kt`.
/// 유럽 등 동의가 필요한 지역에서만 창이 뜬다. 광고는 canRequestAds 가 된 뒤에만 시작한다.
/// 띄울 문구는 AdMob 콘솔 → 개인정보 보호 및 메시지 에서 만든다.
@MainActor
final class Consent {

    var canRequestAds: Bool { ConsentInformation.shared.canRequestAds }

    var privacyOptionsRequired: Bool {
        ConsentInformation.shared.privacyOptionsRequirementStatus == .required
    }

    /// - Parameter onCanRequestAds: 여러 번 불릴 수 있다
    func gather(from vc: UIViewController, onCanRequestAds: @escaping () -> Void) {
        // 지난 실행의 동의로 이미 가능하면 기다리지 않는다
        if canRequestAds { onCanRequestAds() }

        ConsentInformation.shared.requestConsentInfoUpdate(with: RequestParameters()) { [weak self] error in
            if let error { NSLog("[Consent] 갱신 실패: \(error)") }
            ConsentForm.loadAndPresentIfRequired(from: vc) { error in
                if let error { NSLog("[Consent] 동의 창: \(error)") }
                if self?.canRequestAds == true { onCanRequestAds() }
            }
        }
    }

    func showPrivacyOptions(from vc: UIViewController) {
        ConsentForm.presentPrivacyOptionsForm(from: vc) { error in
            if let error { NSLog("[Consent] 개인정보 옵션: \(error)") }
        }
    }
}
