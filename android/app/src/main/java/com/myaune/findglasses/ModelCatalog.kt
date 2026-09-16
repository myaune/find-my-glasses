package com.myaune.findglasses

/**
 * 앱이 쓰는 모델·어휘·화질 단계.
 *
 * 데스크탑 추정이 기기별로 크게 틀렸다. 같은 데스크탑 수치에서
 * GDINO 는 7배, YOLO-World 는 36배로 벌어졌다. 데스크탑은 PyTorch,
 * 폰은 ONNX Runtime 이라 애초에 같은 조건이 아니었다.
 * 그래서 비교를 폰으로 옮긴다.
 *
 * 모델은 dynamic 으로 익스포트해서 해상도를 런타임에 바꿀 수 있다.
 */
object ModelCatalog {

    data class Entry(
        val label: String,
        val asset: String,
        /** 이 모델이 내는 출력 개수. YOLOE 는 seg 라 2개다. */
        val outputs: Int,
        val note: String,
    )

    /**
     * 클래스 순서. 모든 모델을 같은 어휘로 익스포트했다.
     * 채널 0..3 은 박스, 4..4+nc 가 이 순서의 클래스 점수다.
     *
     * 중요: 클래스 수를 채널 수에서 역산하면 안 된다. YOLOE 는 뒤에 마스크
     * 계수 32 채널이 더 붙어 [1, 43, N] 이고, 역산하면 39개로 잘못 읽는다.
     */
    val CLASSES = listOf(
        "a pair of eyeglasses",   // 0 — 양성
        "keys",
        "phone",
        "scissors",
        "pen",
        "remote control",
        "cup",
        "car key",                // 7 — 2026-09-13 추가 (차 스마트키)
    )

    /**
     * 찾을 대상. 앱을 켜면 항상 안경이다.
     *
     * 안경 외에는 **테스트하지 않은 부가 기능**이다. 원래 오탐을 흡수하려고 넣은
     * 네거티브 어휘를 대상으로 돌려 쓴다. 신뢰도 단계도 안경 점수 분포로 맞춘
     * 값을 그대로 쓴다.
     */
    enum class Target(val classes: IntArray, val labelRes: Int, val emoji: String) {
        GLASSES(intArrayOf(0), R.string.target_glasses, "👓"),
        KEYS(intArrayOf(1, 7), R.string.target_keys, "🔑"),
        PHONE(intArrayOf(2), R.string.target_phone, "📱"),
        REMOTE(intArrayOf(5), R.string.target_remote, "📺"),
    }

    /** letterbox 패딩색 (ultralytics 기본값). GDINO 는 0 이었다. */
    const val PAD_GRAY = 114

    /**
     * YOLO-World s 하나만 남겼다.
     *
     * 데스크탑 사진 17장 검출률(임계 0.40) 과 속도를 같이 보면 나머지를 남길
     * 이유가 없었다.
     *   YOLO-World s   89ms   3/17
     *   YOLO-World m  172ms   3/17   2배 느리고 검출은 같다
     *   YOLOE 11s      85ms   1/17   더 나쁘다
     *
     * 실기기 테스트 결론도 같았다 — 모델 변형 차이보다 입력 해상도 차이가
     * 압도적이다. 예산을 해상도에 쓴다.
     */
    /**
     * FP16 도 넣어봤지만 실기기에서 점수가 전혀 움직이지 않았다 (데스크탑에서는
     * 점수 최대차 0.0001 로 멀쩡했다). 원인을 파지 않고 FP32 로 확정했다.
     * poc/scripts/yolo_fp16.py 는 남겨둔다.
     */
    val MODELS = listOf(
        Entry(
            label = "YOLO-World s",
            asset = "yolo-world-s-v2.onnx",
            outputs = 1,
            note = "49.5MB · 416px 에서 검출 가능, 그 아래로는 떨어진다",
        ),
    )

    /**
     * 사용자에게 보여주는 화질 단계.
     *
     * 해상도를 올리면 작은 안경을 더 잘 잡지만 프레임이 떨어진다. 폰 성능이
     * 제각각이라 사용자가 고르게 한다. 416 아래는 실기기에서 검출이 거의 안 돼
     * 사용자 선택지에서 뺐다.
     */
    data class Quality(val size: Int, val labelRes: Int)

    val QUALITIES = listOf(
        Quality(416, R.string.quality_normal),
        Quality(512, R.string.quality_high),
        Quality(640, R.string.quality_max),
    )
}
