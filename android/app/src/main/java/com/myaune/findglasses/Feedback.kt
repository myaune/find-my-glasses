package com.myaune.findglasses

import android.content.Context
import android.media.AudioManager
import android.media.AudioAttributes
import android.os.Build
import android.os.VibrationAttributes
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.speech.tts.TextToSpeech
import android.util.Log
import java.util.Locale

/**
 * 음성과 진동 (기획서 4절).
 *
 * 음성은 시력 때문이 아니라 **화면 대신 방을 보면서 쓸 수 있게** 넣는다.
 *
 * 1차 구현은 상태를 계속 말했다. 타깃이 보이는 동안 3.5초마다 "여기예요" 를
 * 반복했고, 스윕 속도가 한계 근처에서 흔들릴 때마다 "조금만 천천히" 를 말했다.
 * 실사용에서 거슬렸다. 그래서 **변화가 있을 때만** 알린다.
 *
 *   타깃이 처음 나타날 때       한 번
 *   신뢰도 단계가 올라갈 때     한 번 (내려갈 때는 조용히)
 *   타깃을 한동안 놓쳤다 다시 찾을 때  한 번
 *   너무 빠를 때               최소 15초 간격
 *
 * 진동도 연속으로 떨지 않고 같은 사건에 짧게 큐만 준다. 단계가 높을수록 톡
 * 횟수가 늘어 화면을 안 봐도 구분된다.
 *
 * 찾았다를 누른 뒤에는 음소거한다. 축하 화면과 광고가 뜨는 동안 "여기예요" 가
 * 계속 나왔다.
 */
class Feedback(private val context: Context) {

    private val vibrator: Vibrator? = if (Build.VERSION.SDK_INT >= 31) {
        context.getSystemService(VibratorManager::class.java)?.defaultVibrator
    } else {
        @Suppress("DEPRECATION")
        context.getSystemService(Vibrator::class.java)
    }

    private val audio: AudioManager? = context.getSystemService(AudioManager::class.java)

    private var tts: TextToSpeech? = null
    private var ttsReady = false

    var voiceEnabled = true
    var vibrationEnabled = true

    /** 찾았다 이후 광고가 끝날 때까지 */
    var muted = false
        set(v) {
            field = v
            if (v) tts?.stop()
        }

    private var lastTier: Confidence? = null
    private var lostSinceMs = 0L
    private var lastTooFastSpokenMs = 0L

    init {
        tts = TextToSpeech(context) { status ->
            if (status != TextToSpeech.SUCCESS) return@TextToSpeech
            // 기기 언어가 아니라 **앱이 실제로 고른 문자열의 언어**로 말한다.
            // 기기가 독일어면 앱은 영어 문자열로 떨어지는데, 그때 독일어 TTS 로
            // 영어 문장을 읽으면 이상하다. values-*/strings.xml 에 tts_locale 을
            // 둬서 어느 언어 묶음이 선택됐는지 알아낸다.
            val tag = context.getString(R.string.tts_locale)
            val want = Locale.forLanguageTag(tag)
            val engine = tts ?: return@TextToSpeech
            val ok = engine.isLanguageAvailable(want) >= TextToSpeech.LANG_AVAILABLE
            if (ok) {
                engine.language = want
                ttsReady = true
            } else if (engine.isLanguageAvailable(Locale.US) >= TextToSpeech.LANG_AVAILABLE
                && tag.startsWith("en")
            ) {
                engine.language = Locale.US
                ttsReady = true
            } else {
                // 그 언어 음성이 기기에 없으면 다른 언어로 억지로 말하지 않는다.
                Log.i(TAG, "TTS 에 $tag 가 없어 음성 안내를 끈다")
            }
        }
    }

    /**
     * 매 화면 갱신마다 부른다. 변화가 있을 때만 실제로 알린다.
     * @param conf 현재 타깃의 신뢰도. 타깃이 없으면 null
     */
    fun onTarget(conf: Confidence?, nowMs: Long) {
        if (muted) return
        if (conf == null) {
            if (lastTier != null && lostSinceMs == 0L) lostSinceMs = nowMs
            // 잠깐 가려진 건 놓친 걸로 보지 않는다
            if (lostSinceMs != 0L && nowMs - lostSinceMs > LOST_RESET_MS) lastTier = null
            return
        }
        lostSinceMs = 0L

        val prev = lastTier
        if (prev == null || conf.ordinal > prev.ordinal) {
            lastTier = conf
            speak(voiceFor(conf))
            tap(conf)
        } else if (conf.ordinal < prev.ordinal) {
            // 내려갈 때는 조용히 기록만 한다. 다시 올라가면 알린다.
            lastTier = conf
        }
    }

    fun onTooFast(nowMs: Long) {
        if (muted) return
        if (nowMs - lastTooFastSpokenMs < TOO_FAST_GAP_MS) return
        lastTooFastSpokenMs = nowMs
        speak(context.getString(R.string.voice_too_fast))
    }

    fun success() {
        speak(context.getString(R.string.voice_found), force = true)
        vibrate(longArrayOf(0, 100, 90, 100, 90, 220), intArrayOf(0, 200, 0, 200, 0, 255))
    }

    fun reset() {
        lastTier = null
        lostSinceMs = 0L
    }

    private fun voiceFor(c: Confidence) = context.getString(
        when (c) {
            Confidence.HIGH -> R.string.voice_high
            Confidence.MEDIUM -> R.string.voice_medium
            Confidence.LOW -> R.string.voice_low
        }
    )

    private fun speak(text: String, force: Boolean = false) {
        if (!voiceEnabled || !ttsReady || text.isEmpty()) return
        // 폰이 무음·진동 모드면 말하지 않는다. TTS 는 미디어 볼륨으로 나가서
        // 그냥 두면 무음 모드에서도 소리가 난다.
        if (audio != null && audio.ringerMode != AudioManager.RINGER_MODE_NORMAL) return
        if (muted && !force) return
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "fg")
    }

    /**
     * 단계 큐. 과하지 않게 짧은 톡을 단계만큼 준다.
     *   낮음 톡 / 중간 톡톡 / 높음 톡톡톡
     */
    private fun tap(c: Confidence) {
        val n = c.ordinal + 1
        val timings = LongArray(n * 2)
        val amps = IntArray(n * 2)
        for (i in 0 until n) {
            timings[i * 2] = if (i == 0) 0 else TAP_GAP_MS
            timings[i * 2 + 1] = TAP_MS
            amps[i * 2] = 0
            amps[i * 2 + 1] = c.vibeAmplitude
        }
        vibrate(timings, amps)
    }

    /**
     * 음소거 판단은 호출하는 쪽이 한다 (success 는 음소거 직전에 부른다).
     *
     * 1차 구현(45ms, 세기 60)은 Redmi Note 13 4G 에서 전혀 느껴지지 않았다.
     * 저가폰의 편심 모터는 켜지는 데 시간이 걸려 짧고 약한 펄스는 돌기 전에
     * 끝난다. 펄스를 늘리고 세기를 올렸다.
     *
     * 용도를 접근성으로 표시한다. 용도 없는 진동은 기기 설정(터치 진동 끔
     * 등)에 따라 걸러질 수 있다.
     */
    private fun vibrate(timings: LongArray, amps: IntArray) {
        if (!vibrationEnabled) return
        // 폰이 무음 모드면 떨지 않는다 (진동 모드는 떤다)
        if (audio?.ringerMode == AudioManager.RINGER_MODE_SILENT) return
        val v = vibrator ?: return
        if (!v.hasVibrator()) return
        if (Build.VERSION.SDK_INT >= 26) {
            // 세기 조절을 지원하지 않는 기기는 기본 세기로 떤다
            val a = if (v.hasAmplitudeControl()) amps
            else IntArray(amps.size) { if (amps[it] > 0) VibrationEffect.DEFAULT_AMPLITUDE else 0 }
            val effect = VibrationEffect.createWaveform(timings, a, -1)
            if (Build.VERSION.SDK_INT >= 33) {
                v.vibrate(effect, VibrationAttributes.createForUsage(VibrationAttributes.USAGE_ACCESSIBILITY))
            } else {
                @Suppress("DEPRECATION")
                v.vibrate(effect, AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY).build())
            }
        } else {
            @Suppress("DEPRECATION")
            v.vibrate(timings, -1)
        }
    }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
    }

    companion object {
        private const val TAG = "Feedback"

        /** 이만큼 타깃을 놓치면 다음에 찾았을 때 다시 알린다 */
        private const val LOST_RESET_MS = 4000L

        /** "조금만 천천히" 최소 간격 */
        private const val TOO_FAST_GAP_MS = 15000L

        /** 톡 한 번 길이와 톡 사이 간격 */
        private const val TAP_MS = 100L
        private const val TAP_GAP_MS = 110L
    }
}
