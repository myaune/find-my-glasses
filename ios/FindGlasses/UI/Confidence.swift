import UIKit

/// 신뢰도 단계. Android `Confidence.kt` 와 같은 값.
/// 색 하나에 의존하지 않고 색 + 문구 + 펄스 속도로 3중 표기한다 (안경을 안 쓴 사용자 전제).
enum Confidence: Int, CaseIterable {
    case low, medium, high

    var minScore: Float {
        switch self {
        case .low: return 0
        case .medium: return 0.16
        case .high: return 0.30
        }
    }

    /// 노랑 → 연두 → 초록
    var color: UIColor {
        switch self {
        case .low: return UIColor(red: 255 / 255, green: 214 / 255, blue: 0, alpha: 1)
        case .medium: return UIColor(red: 180 / 255, green: 220 / 255, blue: 30 / 255, alpha: 1)
        case .high: return UIColor(red: 40 / 255, green: 215 / 255, blue: 90 / 255, alpha: 1)
        }
    }

    var messageKey: String {
        switch self {
        case .low: return "conf_low"
        case .medium: return "conf_medium"
        case .high: return "conf_high"
        }
    }

    var voiceKey: String {
        switch self {
        case .low: return "voice_low"
        case .medium: return "voice_medium"
        case .high: return "voice_high"
        }
    }

    /// 펄스 한 주기 (초). 짧을수록 급하게 깜빡인다.
    var pulse: Double {
        switch self {
        case .low: return 1.4
        case .medium: return 0.9
        case .high: return 0.52
        }
    }

    /// 진동 세기 0~1 (Android 140/200/255)
    var hapticIntensity: Float {
        switch self {
        case .low: return 0.55
        case .medium: return 0.78
        case .high: return 1
        }
    }

    static func of(_ score: Float) -> Confidence {
        if score >= Confidence.high.minScore { return .high }
        if score >= Confidence.medium.minScore { return .medium }
        return .low
    }
}

/// 현지화 문구
func L(_ key: String) -> String {
    NSLocalizedString(key, comment: "")
}
