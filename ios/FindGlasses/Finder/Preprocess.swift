import CoreGraphics
import Foundation

/// 카메라 프레임을 모델 입력 텐서로 바꾼다. Android `Preprocess.kt` 와 같은 동작.
///
/// YOLO-World: letterbox 패딩 114, /255 만 한다 (ImageNet 정규화를 넣으면 검출이 무너진다).
final class Preprocess {

    /// letterbox 파라미터. 박스를 원본 좌표로 되돌릴 때 쓴다.
    struct Fit {
        let scale: CGFloat
        let padX: Int
        let padY: Int
        let srcW: Int
        let srcH: Int
    }

    let size: Int
    private let context: CGContext
    /// 매 프레임 새로 할당하지 않고 재사용한다
    private(set) var chw: [Float]

    init?(size: Int) {
        self.size = size
        guard let ctx = CGContext(
            data: nil, width: size, height: size, bitsPerComponent: 8, bytesPerRow: size * 4,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue
        ) else { return nil }
        ctx.interpolationQuality = .medium
        context = ctx
        chw = [Float](repeating: 0, count: 3 * size * size)
    }

    /// - Parameter image: 똑바로 세운 프레임 (회전은 카메라 연결에서 이미 맞춘다)
    func run(_ image: CGImage) -> Fit {
        let w = image.width
        let h = image.height
        let scale = CGFloat(size) / CGFloat(max(w, h))
        // 데스크탑이 round 를 쓴다. 절삭하면 1px 어긋난다.
        let nw = max(1, Int((CGFloat(w) * scale).rounded()))
        let nh = max(1, Int((CGFloat(h) * scale).rounded()))
        let padX = (size - nw) / 2
        let padY = (size - nh) / 2

        let g = CGFloat(ModelCatalog.padGray) / 255
        context.setFillColor(red: g, green: g, blue: g, alpha: 1)
        context.fill(CGRect(x: 0, y: 0, width: size, height: size))
        // CoreGraphics 는 원점이 왼쪽 아래다. 위에서 padY 떨어진 자리에 그리려면 뒤집는다.
        context.draw(image, in: CGRect(x: padX, y: size - padY - nh, width: nw, height: nh))

        if let data = context.data {
            let px = data.bindMemory(to: UInt8.self, capacity: size * size * 4)
            let plane = size * size
            chw.withUnsafeMutableBufferPointer { out in
                for i in 0..<plane {
                    out[i] = Float(px[i * 4]) / 255
                    out[plane + i] = Float(px[i * 4 + 1]) / 255
                    out[2 * plane + i] = Float(px[i * 4 + 2]) / 255
                }
            }
        }
        return Fit(scale: scale, padX: padX, padY: padY, srcW: w, srcH: h)
    }
}
