import AVFoundation
import CoreHaptics
import UIKit

/// 음성과 진동. Android `Feedback.kt` 의 이식.
///
/// 변화가 있을 때만 알린다 — 타깃이 처음 나타날 때, 신뢰도 단계가 올라갈 때,
/// 한동안 놓쳤다 다시 찾을 때, 너무 빠를 때(최소 15초 간격).
/// 진동은 같은 사건에 짧은 톡을 단계만큼 준다 (낮음 톡 / 중간 톡톡 / 높음 톡톡톡).
///
/// 무음 스위치: 오디오 세션을 `.ambient` 로 두면 무음 스위치가 켜졌을 때 음성이 자동으로
/// 나오지 않는다 (Android 에서 벨소리 모드를 직접 확인하던 것에 해당).
/// 진동은 시스템 햅틱 설정을 따른다.
@MainActor
final class Feedback {

    var voiceEnabled = true
    var vibrationEnabled = true

    /// 찾았다 이후 광고가 끝날 때까지
    var muted = false {
        didSet { if muted { synth.stopSpeaking(at: .immediate) } }
    }

    private let synth = AVSpeechSynthesizer()
    private var voice: AVSpeechSynthesisVoice?
    private var haptics: CHHapticEngine?

    private var lastTier: Confidence?
    private var lostSince: Double = 0
    private var lastTooFastSpoken: Double = -.infinity

    private static let lostResetMs: Double = 4000
    private static let tooFastGapMs: Double = 15000
    private static let tapDuration = 0.10
    private static let tapGap = 0.11

    init() {
        try? AVAudioSession.sharedInstance().setCategory(.ambient, options: [.mixWithOthers, .duckOthers])

        // 기기 언어가 아니라 앱이 실제로 고른 문자열의 언어로 말한다.
        // 그 언어 음성이 기기에 없으면 다른 언어로 억지로 말하지 않는다.
        let tag = L("tts_locale")
        voice = AVSpeechSynthesisVoice(language: tag)
            ?? AVSpeechSynthesisVoice(language: String(tag.prefix(2)))

        if CHHapticEngine.capabilitiesForHardware().supportsHaptics {
            haptics = try? CHHapticEngine()
            haptics?.resetHandler = { [weak self] in try? self?.haptics?.start() }
            try? haptics?.start()
        }
    }

    /// 매 화면 갱신마다 불러도 된다. 변화가 있을 때만 알린다.
    func onTarget(_ conf: Confidence?, nowMs: Double) {
        if muted { return }
        guard let conf else {
            if lastTier != nil && lostSince == 0 { lostSince = nowMs }
            if lostSince != 0 && nowMs - lostSince > Self.lostResetMs { lastTier = nil }
            return
        }
        lostSince = 0
        if let prev = lastTier, conf.rawValue <= prev.rawValue {
            if conf.rawValue < prev.rawValue { lastTier = conf }  // 내려갈 때는 조용히
            return
        }
        lastTier = conf
        speak(L(conf.voiceKey))
        tap(conf)
    }

    func onTooFast(nowMs: Double) {
        if muted || nowMs - lastTooFastSpoken < Self.tooFastGapMs { return }
        lastTooFastSpoken = nowMs
        speak(L("voice_too_fast"))
    }

    /// 음소거 직전에 부른다
    func success() {
        speak(L("voice_found"), force: true)
        play(events: [(0, 0.8), (0.19, 0.8), (0.38, 1.0)], duration: 0.12)
    }

    func reset() {
        lastTier = nil
        lostSince = 0
    }

    private func speak(_ text: String, force: Bool = false) {
        guard voiceEnabled, let voice, !text.isEmpty else { return }
        if muted && !force { return }
        synth.stopSpeaking(at: .immediate)
        let u = AVSpeechUtterance(string: text)
        u.voice = voice
        synth.speak(u)
    }

    private func tap(_ c: Confidence) {
        let n = c.rawValue + 1
        let events = (0..<n).map { (Double($0) * (Self.tapDuration + Self.tapGap), c.hapticIntensity) }
        play(events: events, duration: Self.tapDuration)
    }

    private func play(events: [(Double, Float)], duration: Double) {
        guard vibrationEnabled else { return }
        guard let engine = haptics else {
            UIImpactFeedbackGenerator(style: .heavy).impactOccurred()
            return
        }
        let hapticEvents = events.map { t, intensity in
            CHHapticEvent(
                eventType: .hapticContinuous,
                parameters: [
                    CHHapticEventParameter(parameterID: .hapticIntensity, value: intensity),
                    CHHapticEventParameter(parameterID: .hapticSharpness, value: 0.5),
                ],
                relativeTime: t, duration: duration)
        }
        do {
            let player = try engine.makePlayer(with: CHHapticPattern(events: hapticEvents, parameters: []))
            try player.start(atTime: CHHapticTimeImmediate)
        } catch {
            NSLog("[Feedback] 햅틱 실패: \(error)")
        }
    }
}
