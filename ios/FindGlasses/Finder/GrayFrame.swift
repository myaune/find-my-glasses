import CoreGraphics
import CoreVideo

/// 카메라 프레임(BGRA, 이미 똑바로 세움)에서 추적용 흑백 축소본을 뽑는다. Android `GrayFrame.kt`.
/// 추론이 도는 동안 30fps 로 불리므로 할당 없이 버퍼를 바로 샘플링한다.
final class GrayFrame {

    private(set) var data: [UInt8] = []
    private(set) var width = 0
    private(set) var height = 0
    /// 축소본 1픽셀이 원본 프레임의 몇 픽셀인가
    private(set) var scale: CGFloat = 1

    private let targetLongSide: Int

    init(targetLongSide: Int = 192) {
        self.targetLongSide = targetLongSide
    }

    func fill(_ pb: CVPixelBuffer) -> Bool {
        guard CVPixelBufferGetPixelFormatType(pb) == kCVPixelFormatType_32BGRA else { return false }
        CVPixelBufferLockBaseAddress(pb, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pb, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddress(pb) else { return false }

        let srcW = CVPixelBufferGetWidth(pb)
        let srcH = CVPixelBufferGetHeight(pb)
        let stride = CVPixelBufferGetBytesPerRow(pb)
        let step = max(1, max(srcW, srcH) / targetLongSide)
        let w = srcW / step
        let h = srcH / step
        if w < 8 || h < 8 { return false }

        if data.count != w * h { data = [UInt8](repeating: 0, count: w * h) }
        width = w
        height = h
        scale = CGFloat(step)

        let px = base.assumingMemoryBound(to: UInt8.self)
        data.withUnsafeMutableBufferPointer { out in
            var i = 0
            for y in 0..<h {
                let row = y * step * stride
                for x in 0..<w {
                    let p = row + x * step * 4
                    let b = Int(px[p]), g = Int(px[p + 1]), r = Int(px[p + 2])
                    // 정수 근사 휘도. 추적용이라 정확할 필요가 없다.
                    out[i] = UInt8((r * 77 + g * 150 + b * 29) >> 8)
                    i += 1
                }
            }
        }
        return true
    }
}
