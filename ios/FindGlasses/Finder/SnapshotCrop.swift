import CoreGraphics
import UIKit

/// 찾았을 때 보여줄 사진. 추론에 들어간 프레임에서 검출 박스 주변을 잘라낸다. Android `SnapshotCrop.kt`.
enum SnapshotCrop {

    /// - Parameters:
    ///   - image: 똑바로 세운 프레임
    ///   - box: 같은 프레임 좌표
    ///   - padRatio: 박스 크기 대비 여백. 안경만 딱 자르면 어디인지 맥락이 없다.
    static func crop(_ image: CGImage, box: CGRect, padRatio: CGFloat = 0.6, maxSide: CGFloat = 720) -> UIImage? {
        let iw = CGFloat(image.width), ih = CGFloat(image.height)
        let padX = box.width * padRatio
        let padY = box.height * padRatio
        // 너무 작은 검출도 알아볼 수 있게 최소 크기를 준다
        let minSide = min(iw, ih) * 0.35
        let halfW = max(box.width / 2 + padX, minSide / 2)
        let halfH = max(box.height / 2 + padY, minSide / 2)

        let l = (box.midX - halfW).rounded().clamped(0, iw - 1)
        let t = (box.midY - halfH).rounded().clamped(0, ih - 1)
        let r = (box.midX + halfW).rounded().clamped(l + 1, iw)
        let b = (box.midY + halfH).rounded().clamped(t + 1, ih)

        // CGImage.cropping 은 이미지 픽셀 좌표(원점 왼쪽 위)를 쓴다
        guard let cut = image.cropping(to: CGRect(x: l, y: t, width: r - l, height: b - t)) else { return nil }

        let s = maxSide / max(CGFloat(cut.width), CGFloat(cut.height))
        if s >= 1 { return UIImage(cgImage: cut) }
        let size = CGSize(width: CGFloat(cut.width) * s, height: CGFloat(cut.height) * s)
        return UIGraphicsImageRenderer(size: size).image { _ in
            UIImage(cgImage: cut).draw(in: CGRect(origin: .zero, size: size))
        }
    }
}
