import CoreMotion
import Foundation

/// 자이로 → 회전행렬. Android `SensorManager.getRotationMatrixFromVector` 와 같은 식으로 만든다.
///
/// Android 의 회전벡터와 CoreMotion 의 자세 쿼터니언을 같은 규약(기기좌표 → 월드)으로 보고
/// 같은 공식을 쓴다. 기기 축도 같다 (X 오른쪽, Y 위, Z 화면 밖).
///
/// ⚠️ 실기기 확인 필요: 폰을 위로 돌렸을 때 네모가 아래로 가야 맞다. 반대로 가면
/// [transpose] 를 true 로 바꾼다 (규약이 반대라는 뜻).
final class Motion {

    static let transpose = false

    private let manager = CMMotionManager()
    private let queue: OperationQueue = {
        let q = OperationQueue()
        q.name = "motion"
        q.maxConcurrentOperationCount = 1
        return q
    }()

    var isAvailable: Bool { manager.isDeviceMotionAvailable }

    /// - Parameter onRotation: 모션 큐에서 불린다
    func start(onRotation: @escaping ([Float], Double) -> Void) {
        guard manager.isDeviceMotionAvailable else { return }
        manager.deviceMotionUpdateInterval = 1.0 / 60
        manager.startDeviceMotionUpdates(using: .xArbitraryZVertical, to: queue) { motion, _ in
            guard let q = motion?.attitude.quaternion else { return }
            onRotation(Self.matrix(q), CACurrentMediaTimeMs())
        }
    }

    func stop() {
        manager.stopDeviceMotionUpdates()
    }

    static func matrix(_ q: CMQuaternion) -> [Float] {
        let x = Float(q.x), y = Float(q.y), z = Float(q.z), w = Float(q.w)
        let r: [Float] = [
            1 - 2 * y * y - 2 * z * z, 2 * x * y - 2 * z * w, 2 * x * z + 2 * y * w,
            2 * x * y + 2 * z * w, 1 - 2 * x * x - 2 * z * z, 2 * y * z - 2 * x * w,
            2 * x * z - 2 * y * w, 2 * y * z + 2 * x * w, 1 - 2 * x * x - 2 * y * y,
        ]
        guard transpose else { return r }
        return [r[0], r[3], r[6], r[1], r[4], r[7], r[2], r[5], r[8]]
    }
}

/// 단조 증가 시각 (ms)
func CACurrentMediaTimeMs() -> Double {
    ProcessInfo.processInfo.systemUptime * 1000
}
