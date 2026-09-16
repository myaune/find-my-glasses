import Foundation

/// 광고 제거 IAP (non-consumable, 약 $1.5). Android `Purchases.kt` 와 같은 구조.
///
/// 지금은 구조만 있다. 설정의 광고 없애기 카드 / 구매 복원과 결과 처리는 연결돼 있고,
/// 실제 결제만 [PlaceholderPurchases] 가 "아직 준비 중" 으로 막는다.
///
/// 붙일 때 할 일 (StoreKit 2)
///   - App Store Connect 에 비소모성 상품 등록 (예: remove_ads), 국가별 가격
///   - `Product.products(for:)` 로 displayPrice 를 받아 [removeAdsPrice]
///   - `Transaction.currentEntitlements` 로 보유 여부 → [adFree]
///   - 구매 복원 버튼은 `AppStore.sync()` — 없으면 심사에서 리젝된다
@MainActor
protocol Purchases: AnyObject {
    var adFree: Bool { get }
    /// 스토어가 준 현지 가격. 모르면 nil → 가격 없이 표시
    func removeAdsPrice() async -> String?
    func buyRemoveAds() async -> PurchaseResult
    func restore() async -> PurchaseResult
}

enum PurchaseResult {
    case purchased, restored, nothingToRestore, cancelled
    /// 결제를 쓸 수 없음 (아직 미구현, 스토어 미연결 등)
    case unavailable
}

@MainActor
final class PlaceholderPurchases: Purchases {
    let adFree = false
    func removeAdsPrice() async -> String? { nil }
    func buyRemoveAds() async -> PurchaseResult { .unavailable }
    func restore() async -> PurchaseResult { .unavailable }
}
