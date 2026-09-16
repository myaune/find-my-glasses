import AVFoundation
import SwiftUI
import UIKit

/// 안경 찾기 본체. Android `MainActivity.kt` 의 찾기 로직 이식.
///
///   Camera ─ 최신 프레임 (30fps, 분석 큐)
///     ├─ 추론이 노는 중이면 → 복사해서 추론 큐로 (1초 안팎)
///     └─ 추론이 도는 중이면 → 그 프레임으로 패치 추적 (이동 보정)
///   Motion ─ 자이로 60Hz → Tracker 회전 보정, 스윕 속도
///   Tracker ─ 위치 유지 + temporal filter → OverlayView 네모 하나
///   Feedback ─ 음성 + 진동
///
/// 추론이 느린 것을 전제로 한다. 프레임 사이를 추적으로 메우는 것이 핵심이다.
@MainActor
final class FinderEngine: ObservableObject {

    // ── 화면 상태 ─────────────────────────────────────────────
    @Published var loading = true
    @Published var hintKey: String? = "searching"
    @Published var showFoundButton = false
    @Published var celebrating = false
    @Published var snapshot: UIImage?
    @Published var tutorialOpen = false {
        didSet { state.isTutorialOpen = tutorialOpen }
    }
    @Published var target: ModelCatalog.Target = .glasses
    @Published var inputSize: Int
    @Published var cameraDenied = false

    let overlay = OverlayView()
    let confetti = ConfettiView()
    let camera = Camera()
    let feedback = Feedback()
    let ads = Ads()
    let consent = Consent()
    let purchases: Purchases = PlaceholderPurchases()

    // ── 찾기 파이프라인 (백그라운드 스레드) ─────────────────────
    private let motion = Motion()
    private let tracker = Tracker()
    private let patch = PatchTracker()
    private let gray = GrayFrame()
    private let sweep = SweepGuide()
    private let inferQueue = DispatchQueue(label: "infer", qos: .userInitiated)
    private let state = PipelineState()

    private static let celebrateSeconds = 2.8
    private static let prefInputSize = "input_size"
    static let prefTutorialSeen = "tutorial_seen"
    static let prefVoice = "voice"
    static let prefVibration = "vibration"

    init() {
        let saved = UserDefaults.standard.integer(forKey: Self.prefInputSize)
        inputSize = ModelCatalog.qualities.contains { $0.size == saved } ? saved : ModelCatalog.qualities[0].size
        let d = UserDefaults.standard
        feedback.voiceEnabled = d.object(forKey: Self.prefVoice) as? Bool ?? true
        feedback.vibrationEnabled = d.object(forKey: Self.prefVibration) as? Bool ?? true
        ads.enabled = !purchases.adFree
        tutorialOpen = !d.bool(forKey: Self.prefTutorialSeen)
        state.isTutorialOpen = tutorialOpen
    }

    private var cameraStarted = false

    /// 화면이 뜰 때 한 번
    func start() async {
        // 모델 로딩은 튜토리얼과 무관하게 바로 시작한다. 사용자가 튜토리얼을 읽는 동안 끝나 있는 게 낫다.
        await loadDetector()
        // 첫 실행이면 튜토리얼을 닫을 때 카메라 권한을 묻는다
        if !tutorialOpen { await startCamera() }
    }

    private func startCamera() async {
        guard !cameraStarted else { return }
        cameraStarted = true
        guard await Camera.requestAccess() else {
            cameraDenied = true
            return
        }
        do {
            try camera.configure()
        } catch {
            NSLog("[Finder] 카메라 설정 실패: \(error)")
            return
        }
        camera.onFrame = { [weak self] pb in self?.analyze(pb) }
        camera.start()
        motion.start { [weak self] r, now in self?.onRotation(r, nowMs: now) }

        if ads.enabled, let vc = UIApplication.shared.topViewController {
            consent.gather(from: vc) { [weak self] in self?.ads.start() }
        }
    }

    func pause() {
        guard cameraStarted else { return }
        camera.stop()
        motion.stop()
    }

    func resume() {
        guard cameraStarted, !cameraDenied else { return }
        camera.start()
        motion.start { [weak self] r, now in self?.onRotation(r, nowMs: now) }
    }

    // ── 모델 ─────────────────────────────────────────────────
    private func loadDetector() async {
        loading = true
        let size = inputSize
        let classes = target.classes
        let detector: YoloDetector? = await withCheckedContinuation { cont in
            inferQueue.async {
                guard let path = Bundle.main.path(forResource: ModelCatalog.modelResource, ofType: "onnx") else {
                    NSLog("[Finder] 번들에 모델이 없다 — ios/README.md 의 모델 복사 단계")
                    cont.resume(returning: nil)
                    return
                }
                do {
                    let t0 = CFAbsoluteTimeGetCurrent()
                    let d = try YoloDetector(modelPath: path, inputSize: size)
                    d.targetClasses = classes
                    NSLog("[Finder] \(size)px \(d.provider) 로드 \(Int((CFAbsoluteTimeGetCurrent() - t0) * 1000))ms")
                    cont.resume(returning: d)
                } catch {
                    NSLog("[Finder] 모델 로드 실패: \(error)")
                    cont.resume(returning: nil)
                }
            }
        }
        state.setDetector(detector)
        loading = false
    }

    func setQuality(_ size: Int) {
        guard size != inputSize else { return }
        inputSize = size
        UserDefaults.standard.set(size, forKey: Self.prefInputSize)
        resetSession()
        Task { await loadDetector() }
    }

    func setTarget(_ t: ModelCatalog.Target) {
        guard t != target else { return }
        target = t
        state.detector?.targetClasses = t.classes
        resetSession()
    }

    func resetSession() {
        tracker.reset()
        state.resetSession()
        sweep.reset()
        feedback.reset()
        snapshot = nil
        showFoundButton = false
        overlay.setTarget(nil, confidence: .low, message: "")
    }

    // ── 튜토리얼 ─────────────────────────────────────────────
    func openTutorial() {
        tutorialOpen = true
        feedback.muted = true
    }

    func closeTutorial() {
        tutorialOpen = false
        UserDefaults.standard.set(true, forKey: Self.prefTutorialSeen)
        if !celebrating { feedback.muted = false }
        Task { await startCamera() }
    }

    // ── 분석 (분석 큐) ───────────────────────────────────────
    nonisolated private func analyze(_ pb: CVPixelBuffer) {
        let fw = CVPixelBufferGetWidth(pb)
        let fh = CVPixelBufferGetHeight(pb)
        let captureR = state.latestR
        let now = CACurrentMediaTimeMs()

        tracker.setFocal(camera.focalPx(frameLongSide: max(fw, fh)))
        let grayOk = gray.fill(pb)

        // 추론이 막 끝났으면 템플릿을 다시 심는다 (gray 를 소유한 스레드다)
        if grayOk && state.takeReseed() {
            if let t = tracker.primary(nowMs: now) { patch.seed(gray, box: t.box) }
        } else if grayOk && patch.isActive {
            // 이동 보정 — 추론을 기다리지 않고 매 프레임 반영
            if let shift = patch.track(gray) {
                tracker.applyVisualShift(dx: shift.0, dy: shift.1, rNow: state.latestR)
            }
        }
        if state.patchClearRequested() { patch.clear() }

        // 축하 화면·광고·튜토리얼 중에는 추론하지 않는다 (발열도 줄인다)
        if state.canStartInference() {
            if let image = FrameCopy.cgImage(pb) {
                inferQueue.async { [weak self] in
                    self?.runInference(image, captureR: captureR)
                    self?.state.inferenceDone()
                }
            } else {
                state.inferenceDone()
            }
        }

        publish(fw: fw, fh: fh, nowMs: now)
    }

    nonisolated private func runInference(_ image: CGImage, captureR: [Float]?) {
        guard let d = state.detector else { return }
        let result: DetectResult
        do {
            result = try d.detect(image, threshold: ModelCatalog.threshold)
        } catch {
            NSLog("[Finder] 추론 실패: \(error)")
            return
        }

        // 세션 최고점을 갱신하면 그 순간의 사진을 잘라둔다. 찾았을 때 가운데 띄운다.
        if let top = result.detections.max(by: { $0.score < $1.score }), state.isNewBest(top.score),
           let cut = SnapshotCrop.crop(image, box: top.box) {
            Task { @MainActor in self.snapshot = cut }
        }

        let now = CACurrentMediaTimeMs()
        let fired = tracker.update(result.detections, nowMs: now, captureR: captureR, rNow: state.latestR)

        let interval = result.inferenceMs + result.preprocessMs + result.postprocessMs
        tracker.setFrameInterval(ms: interval)
        if interval > 0 { sweep.setFps(Float(1000 / interval)) }

        // 검출이 나온 자리로 추적 템플릿을 다시 심는다 (실제 seed 는 분석 큐에서)
        state.requestReseed()

        if fired != nil {
            Task { @MainActor in if !self.celebrating { self.showFoundButton = true } }
        }
    }

    /// 화면 갱신. 추론과 무관하게 자주 불린다.
    nonisolated private func publish(fw: Int, fh: Int, nowMs: Double) {
        if state.isCelebrating { return }
        overlay.setFrameSize(width: fw, height: fh)
        let t = tracker.primary(nowMs: nowMs)
        if let t {
            let conf = Confidence.of(t.score)
            overlay.setTarget(t.box, confidence: conf, message: L(conf.messageKey))
        } else {
            overlay.setTarget(nil, confidence: .low, message: "")
        }
        let tooFast = sweep.tooFast
        Task { @MainActor in
            self.hintKey = t == nil ? (tooFast ? "too_fast" : "searching") : nil
            // 변화가 있을 때만 말하고 떤다. 매 프레임 불러도 된다.
            self.feedback.onTarget(t.map { Confidence.of($0.score) }, nowMs: nowMs)
        }
    }

    // ── 자이로 (모션 큐) ─────────────────────────────────────
    nonisolated private func onRotation(_ r: [Float], nowMs: Double) {
        state.latestR = r
        let wasFast = sweep.tooFast
        let fast = sweep.onRotation(r, nowMs: nowMs)
        if fast && !wasFast {
            Task { @MainActor in if !self.celebrating { self.feedback.onTooFast(nowMs: nowMs) } }
        }
        if state.isCelebrating { return }

        // 센서 주기로 회전 보정. 이게 없으면 추론 사이에 네모가 멈춰 있다.
        if tracker.onRotation(r), let t = tracker.primary(nowMs: nowMs) {
            let conf = Confidence.of(t.score)
            overlay.setTarget(t.box, confidence: conf, message: L(conf.messageKey))
        }
    }

    // ── 찾았어요! ────────────────────────────────────────────
    /// 사진을 가운데 띄우고 양옆 폭죽, 몇 초 뒤 전면 광고.
    /// 이 동안 추론과 음성·진동을 멈춘다.
    func onFound() {
        guard !celebrating else { return }
        celebrating = true
        state.isCelebrating = true
        feedback.success()
        feedback.muted = true
        showFoundButton = false
        overlay.setTarget(nil, confidence: .low, message: "")

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) { self.confetti.burst() }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.1) { self.confetti.burst() }
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.celebrateSeconds) {
            guard let vc = UIApplication.shared.topViewController else { self.endCelebration(); return }
            self.ads.showInterstitial(from: vc) { self.endCelebration() }
        }
    }

    private func endCelebration() {
        resetSession()
        celebrating = false
        state.isCelebrating = false
        if !tutorialOpen { feedback.muted = false }
    }
}

/// 여러 스레드가 함께 쓰는 값. 락 하나로 묶는다.
private final class PipelineState: @unchecked Sendable {
    private let lock = NSLock()
    private var _detector: YoloDetector?
    private var _latestR: [Float]?
    private var busy = false
    private var reseed = false
    private var clearPatch = false
    private var bestScore: Float = 0
    private var _celebrating = false
    private var _tutorial = false

    var detector: YoloDetector? { lock.lock(); defer { lock.unlock() }; return _detector }
    func setDetector(_ d: YoloDetector?) { lock.lock(); _detector = d; lock.unlock() }

    var latestR: [Float]? {
        get { lock.lock(); defer { lock.unlock() }; return _latestR }
        set { lock.lock(); _latestR = newValue; lock.unlock() }
    }

    var isCelebrating: Bool {
        get { lock.lock(); defer { lock.unlock() }; return _celebrating }
        set { lock.lock(); _celebrating = newValue; lock.unlock() }
    }

    var isTutorialOpen: Bool {
        get { lock.lock(); defer { lock.unlock() }; return _tutorial }
        set { lock.lock(); _tutorial = newValue; lock.unlock() }
    }

    /// 놀고 있고 멈출 이유가 없으면 busy 로 바꾸고 true
    func canStartInference() -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard !busy, !_celebrating, !_tutorial, _detector != nil else { return false }
        busy = true
        return true
    }

    func inferenceDone() { lock.lock(); busy = false; lock.unlock() }
    func requestReseed() { lock.lock(); reseed = true; lock.unlock() }

    func takeReseed() -> Bool {
        lock.lock(); defer { lock.unlock() }
        let r = reseed
        reseed = false
        return r
    }

    func isNewBest(_ score: Float) -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard score > bestScore else { return false }
        bestScore = score
        return true
    }

    func resetSession() {
        lock.lock()
        bestScore = 0
        clearPatch = true
        lock.unlock()
    }

    func patchClearRequested() -> Bool {
        lock.lock(); defer { lock.unlock() }
        let c = clearPatch
        clearPatch = false
        return c
    }
}
