import AVFoundation
import CoreImage
import UIKit

/// 후면 카메라. 프리뷰와 분석을 같은 세션·같은 16:9 로 묶는다.
///
/// 분석 프레임은 연결에서 세로로 돌려 받는다. 그래서 이후 좌표계는 전부
/// "똑바로 세운 프레임" 하나이고, Android 의 rotationDegrees 처리가 필요 없다.
final class Camera: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {

    let session = AVCaptureSession()
    private let output = AVCaptureVideoDataOutput()
    private let analysisQueue = DispatchQueue(label: "analysis", qos: .userInitiated)

    /// 분석 큐에서 불린다. 버퍼는 콜백 안에서만 쓴다 (풀이 작아 오래 잡으면 프레임이 멈춘다).
    var onFrame: ((CVPixelBuffer) -> Void)?

    static func requestAccess() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: return true
        case .notDetermined: return await AVCaptureDevice.requestAccess(for: .video)
        default: return false
        }
    }

    func configure() throws {
        session.beginConfiguration()
        defer { session.commitConfiguration() }
        session.sessionPreset = .hd1920x1080

        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
            throw NSError(domain: "Camera", code: 1, userInfo: [NSLocalizedDescriptionKey: "후면 카메라 없음"])
        }
        let input = try AVCaptureDeviceInput(device: device)
        if session.canAddInput(input) { session.addInput(input) }

        output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        // 밀린 프레임은 버리고 항상 최신만 본다
        output.alwaysDiscardsLateVideoFrames = true
        output.setSampleBufferDelegate(self, queue: analysisQueue)
        if session.canAddOutput(output) { session.addOutput(output) }

        if let conn = output.connection(with: .video) {
            // 세로로 세운 프레임을 받는다 (iOS 17+)
            if conn.isVideoRotationAngleSupported(90) { conn.videoRotationAngle = 90 }
            conn.isVideoMirrored = false
        }

        // videoFieldOfView 는 센서 긴 변(가로) 방향 화각이다
        longSideFov = CGFloat(device.activeFormat.videoFieldOfView) * .pi / 180
    }

    /// 센서 긴 변 방향 화각 (라디안)
    private(set) var longSideFov: CGFloat = 0

    /// 핀홀 초점거리 = (긴 변 / 2) / tan(화각 / 2). 세운 프레임에서는 긴 변이 세로다.
    func focalPx(frameLongSide: Int) -> CGFloat {
        guard longSideFov > 0 else { return 0 }
        return (CGFloat(frameLongSide) / 2) / tan(longSideFov / 2)
    }

    func start() {
        DispatchQueue.global(qos: .userInitiated).async { [session] in
            if !session.isRunning { session.startRunning() }
        }
    }

    func stop() {
        DispatchQueue.global(qos: .userInitiated).async { [session] in
            if session.isRunning { session.stopRunning() }
        }
    }

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard let pb = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        onFrame?(pb)
    }
}

/// 카메라 버퍼 → CGImage 복사. 추론은 다른 스레드에서 오래 걸리므로 버퍼를 잡지 않고 복사한다.
enum FrameCopy {
    private static let context = CIContext(options: [.useSoftwareRenderer: false])

    static func cgImage(_ pb: CVPixelBuffer) -> CGImage? {
        let ci = CIImage(cvPixelBuffer: pb)
        return context.createCGImage(ci, from: ci.extent)
    }
}

/// 카메라 프리뷰. PreviewView 의 FILL_CENTER 와 같게 resizeAspectFill 로 채운다.
final class CameraPreviewView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }

    init(session: AVCaptureSession) {
        super.init(frame: .zero)
        previewLayer.session = session
        previewLayer.videoGravity = .resizeAspectFill
        backgroundColor = .black
    }

    required init?(coder: NSCoder) { fatalError() }

    override func layoutSubviews() {
        super.layoutSubviews()
        if let conn = previewLayer.connection, conn.isVideoRotationAngleSupported(90) {
            conn.videoRotationAngle = 90
        }
    }
}
