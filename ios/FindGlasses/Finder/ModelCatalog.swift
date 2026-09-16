import CoreGraphics

/// 앱이 쓰는 모델·어휘·화질 단계. Android `ModelCatalog.kt` 와 같은 값이다.
enum ModelCatalog {

    /// 번들에 넣는 모델. Android 와 같은 파일이다 (android/app/src/main/assets/yolo-world-s-v2.onnx).
    /// git 에 올리지 않으므로 빌드 전에 복사한다 — ios/README.md 참고.
    static let modelResource = "yolo-world-s-v2"

    /// 클래스 순서. 출력 채널 4..4+nc 가 이 순서의 점수다.
    /// 클래스 수를 채널 수에서 역산하지 않는다.
    static let classes = [
        "a pair of eyeglasses",  // 0 — 기본 대상
        "keys",                  // 1
        "phone",                 // 2
        "scissors",
        "pen",
        "remote control",        // 5
        "cup",
        "car key",               // 7
    ]

    /// letterbox 패딩색 (ultralytics 기본값)
    static let padGray: UInt8 = 114

    /// 검출 임계값. 실기기에서 0.05 가 맞았다 — 낮은 점수는 신뢰도 단계와 temporal filter 가 거른다.
    static let threshold: Float = 0.05

    /// 찾을 대상. 앱을 켜면 항상 안경이다. 안경 외에는 테스트하지 않은 부가 기능이다.
    enum Target: CaseIterable {
        case glasses, keys, phone, remote

        var classes: Set<Int> {
            switch self {
            case .glasses: return [0]
            case .keys: return [1, 7]
            case .phone: return [2]
            case .remote: return [5]
            }
        }

        var labelKey: String {
            switch self {
            case .glasses: return "target_glasses"
            case .keys: return "target_keys"
            case .phone: return "target_phone"
            case .remote: return "target_remote"
            }
        }

        var emoji: String {
            switch self {
            case .glasses: return "👓"
            case .keys: return "🔑"
            case .phone: return "📱"
            case .remote: return "📺"
            }
        }
    }

    /// 사용자에게 보여주는 화질 단계. 416 아래는 실기기에서 검출이 거의 안 돼 뺐다.
    struct Quality: Hashable {
        let size: Int
        let labelKey: String
    }

    static let qualities = [
        Quality(size: 416, labelKey: "quality_normal"),
        Quality(size: 512, labelKey: "quality_high"),
        Quality(size: 640, labelKey: "quality_max"),
    ]
}

/// 회전 보정된(똑바로 세운) 프레임 좌표(픽셀)의 검출 하나
struct Detection {
    let score: Float
    let box: CGRect
    let classIndex: Int
}

struct DetectResult {
    let detections: [Detection]
    let inferenceMs: Double
    let preprocessMs: Double
    let postprocessMs: Double
    /// 임계값을 넘지 못해도 이 프레임의 최고 대상 점수
    let topPositiveScore: Float
}
