import CoreGraphics
import Foundation
import onnxruntime_objc

/// ONNX Runtime 으로 도는 YOLO-World s. Android `YoloDetector.kt` 와 같은 후처리.
///
/// 어휘가 검출 헤드에 구워져 있어 런타임에 텍스트 인코더가 없다.
/// 출력은 [1, 4+nc, N]
///   채널 0..3     박스 xywh — 입력 픽셀 기준, 정규화 아님
///   채널 4..4+nc  클래스 점수 (sigmoid 적용됨)
///
/// 라이선스: 모델 가중치는 Ultralytics AGPL-3.0. 앱 소스 공개 전제.
final class YoloDetector {

    let provider: String
    let inputSize: Int

    /// 찾을 대상의 클래스 번호. 나머지 어휘는 네거티브가 된다.
    var targetClasses: Set<Int> = ModelCatalog.Target.glasses.classes

    private let env: ORTEnv
    private let session: ORTSession
    private let inputName: String
    private let outputName: String
    private let preprocess: Preprocess
    private let nc = ModelCatalog.classes.count

    private static let maxDetections = 5
    /// 후보가 이미 남긴 박스 안에 이 비율 이상 들어가면 같은 물체로 본다
    private static let containment: CGFloat = 0.65

    init(modelPath: String, inputSize: Int) throws {
        self.inputSize = inputSize
        env = try ORTEnv(loggingLevel: .warning)

        // Core ML 을 먼저 시도하고 안 되면 CPU. 아이폰은 Neural Engine 이 있어
        // Android(NNAPI ≈ CPU) 와 달리 차이가 클 수 있다 — 실기기에서 잰다.
        var created: (ORTSession, String)?
        do {
            let opts = try ORTSessionOptions()
            try opts.appendCoreMLExecutionProvider(with: ORTCoreMLExecutionProviderOptions())
            created = (try ORTSession(env: env, modelPath: modelPath, sessionOptions: opts), "CoreML")
        } catch {
            NSLog("[YoloDetector] CoreML 실패, CPU 로 전환: \(error)")
        }
        if created == nil {
            let opts = try ORTSessionOptions()
            try opts.setIntraOpNumThreads(4)
            created = (try ORTSession(env: env, modelPath: modelPath, sessionOptions: opts), "CPU")
        }
        session = created!.0
        provider = created!.1

        inputName = try session.inputNames().first ?? "images"
        outputName = try session.outputNames().first ?? "output0"
        guard let p = Preprocess(size: inputSize) else {
            throw NSError(domain: "YoloDetector", code: 1, userInfo: [NSLocalizedDescriptionKey: "전처리 버퍼 생성 실패"])
        }
        preprocess = p
    }

    func detect(_ image: CGImage, threshold: Float) throws -> DetectResult {
        let t0 = CFAbsoluteTimeGetCurrent()
        let fit = preprocess.run(image)
        let t1 = CFAbsoluteTimeGetCurrent()

        let s = NSNumber(value: inputSize)
        let data = preprocess.chw.withUnsafeBufferPointer { NSMutableData(bytes: $0.baseAddress, length: $0.count * MemoryLayout<Float>.size) }
        let input = try ORTValue(tensorData: data, elementType: .float, shape: [1, 3, s, s])
        let outputs = try session.run(withInputs: [inputName: input], outputNames: [outputName], runOptions: nil)
        let t2 = CFAbsoluteTimeGetCurrent()

        guard let out = outputs[outputName] else {
            throw NSError(domain: "YoloDetector", code: 2, userInfo: [NSLocalizedDescriptionKey: "출력 없음"])
        }
        let shape = try out.tensorTypeAndShapeInfo().shape.map { $0.intValue }
        let tensor = try out.tensorData() as Data
        let (dets, top) = parse(tensor, anchors: shape[2], fit: fit, threshold: threshold)
        let t3 = CFAbsoluteTimeGetCurrent()

        return DetectResult(
            detections: dets,
            inferenceMs: (t2 - t1) * 1000,
            preprocessMs: (t1 - t0) * 1000,
            postprocessMs: (t3 - t2) * 1000,
            topPositiveScore: top
        )
    }

    private func parse(_ data: Data, anchors: Int, fit: Preprocess.Fit, threshold: Float) -> ([Detection], Float) {
        let targets = targetClasses
        var raw: [Detection] = []
        var topPositive: Float = 0

        data.withUnsafeBytes { (ptr: UnsafeRawBufferPointer) in
            let buf = ptr.bindMemory(to: Float.self)
            for i in 0..<anchors {
                var bestClass = -1
                var bestScore: Float = 0
                var positive: Float = 0
                for c in 0..<nc {
                    let v = buf[(4 + c) * anchors + i]
                    if targets.contains(c), v > positive { positive = v }
                    if v > bestScore { bestScore = v; bestClass = c }
                }
                if positive > topPositive { topPositive = positive }

                // 다른 어휘가 더 높으면 대상이 아니다
                guard targets.contains(bestClass), bestScore >= threshold else { continue }

                let box = toSourceRect(
                    cx: CGFloat(buf[i]), cy: CGFloat(buf[anchors + i]),
                    w: CGFloat(buf[2 * anchors + i]), h: CGFloat(buf[3 * anchors + i]), fit: fit)
                raw.append(Detection(score: bestScore, box: box, classIndex: bestClass))
            }
        }
        raw.sort { $0.score > $1.score }
        return (nms(raw), topPositive)
    }

    /// letterbox 입력 픽셀 xywh → 똑바로 세운 원본 프레임 픽셀
    private func toSourceRect(cx: CGFloat, cy: CGFloat, w: CGFloat, h: CGFloat, fit: Preprocess.Fit) -> CGRect {
        let px = CGFloat(fit.padX), py = CGFloat(fit.padY)
        let x1 = ((cx - w / 2 - px) / fit.scale).clamped(0, CGFloat(fit.srcW))
        let x2 = ((cx + w / 2 - px) / fit.scale).clamped(0, CGFloat(fit.srcW))
        let y1 = ((cy - h / 2 - py) / fit.scale).clamped(0, CGFloat(fit.srcH))
        let y2 = ((cy + h / 2 - py) / fit.scale).clamped(0, CGFloat(fit.srcH))
        return CGRect(x: x1, y: y1, width: x2 - x1, height: y2 - y1)
    }

    /// 같은 안경에 앵커 여러 개가 겹쳐 붙는다. IoU 와 포함 관계로 누른다.
    private func nms(_ sorted: [Detection], iouThreshold: CGFloat = 0.3) -> [Detection] {
        var kept: [Detection] = []
        for d in sorted {
            if !kept.contains(where: { suppresses($0.box, d.box, iouThreshold) }) { kept.append(d) }
            if kept.count >= Self.maxDetections { break }
        }
        return kept
    }

    private func suppresses(_ kept: CGRect, _ cand: CGRect, _ iouThreshold: CGFloat) -> Bool {
        if iou(kept, cand) >= iouThreshold { return true }
        let inter = kept.intersection(cand)
        let candArea = cand.width * cand.height
        if candArea <= 0 { return true }
        if inter.isNull { return false }
        return inter.width * inter.height / candArea >= Self.containment
    }
}

func iou(_ a: CGRect, _ b: CGRect) -> CGFloat {
    let inter = a.intersection(b)
    if inter.isNull || inter.width <= 0 || inter.height <= 0 { return 0 }
    let i = inter.width * inter.height
    let u = a.width * a.height + b.width * b.height - i
    return u > 0 ? i / u : 0
}

extension Comparable {
    func clamped(_ lo: Self, _ hi: Self) -> Self { min(max(self, lo), hi) }
}
