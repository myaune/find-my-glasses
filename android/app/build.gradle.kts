import java.text.SimpleDateFormat
import java.util.Date
import java.util.Properties

/**
 * AdMob 실제 ID 는 android/local.properties 에 둔다 (git 에 안 올라감).
 *
 *   admob.appId=ca-app-pub-XXXXXXXXXXXXXXXX~YYYYYYYYYY
 *   admob.bannerId=ca-app-pub-XXXXXXXXXXXXXXXX/ZZZZZZZZZZ
 *   admob.interstitialId=ca-app-pub-XXXXXXXXXXXXXXXX/WWWWWWWWWW
 *
 * 디버그 빌드는 항상 구글 공개 테스트 ID 를 쓴다. 개발 중에 실제 광고를 띄우고
 * 누르면 AdMob 정책 위반(무효 트래픽)이 될 수 있다. 실제 ID 는 release 에만 들어간다.
 */
val localProps = Properties().apply {
    rootProject.file("local.properties").takeIf { it.exists() }?.inputStream()?.use { load(it) }
}

object AdmobTest {
    const val APP = "ca-app-pub-3940256099942544~3347511713"
    const val BANNER = "ca-app-pub-3940256099942544/6300978111"
    const val INTERSTITIAL = "ca-app-pub-3940256099942544/1033173712"
}

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// 출시 파일 이름에 버전을 넣는다 (예: FindMyGlasses-1.0.2-vc4-release.aab). 덮어쓰지 않게.
// versionCode / versionName 을 올리면 여기도 같이 바꾼다.
base {
    archivesName.set("FindMyGlasses-1.0.2-vc4")
}

android {
    namespace = "com.myaune.findglasses"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.myaune.findglasses"
        minSdk = 26
        // 2026-08-31 부터 새 앱은 API 36 이상을 타깃해야 Play 에 올라간다
        targetSdk = 36
        versionCode = 4
        versionName = "1.0.2"

        // 어느 빌드를 설치했는지 화면에서 확인할 수 있게 시각을 박는다.
        // "빌드가 된 거 맞아?" 를 눌러보고 알 수 있어야 한다.
        buildConfigField(
            "String", "BUILD_TAG",
            "\"" + SimpleDateFormat("MMdd-HHmm").format(Date()) + "\""
        )

        // ONNX Runtime 네이티브 라이브러리가 ABI 마다 들어간다. 4개 다 넣으면
        // 모델 없이도 APK 가 80MB 다. 대상 기기(Redmi Note 13 4G)는 arm64 이고,
        // 출시할 때도 AAB 가 ABI 별로 쪼개 배포하므로 하나만 남긴다.
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
    }

    /**
     * 출시 서명.
     *
     * 비밀번호는 저장소 밖 파일(D:/AppCompany/keys/signing.properties)에만 두고,
     * 환경변수 FINDGLASSES_SIGNING_FILE 이 그 파일을 가리킬 때만 연다.
     * 평소 빌드(개발·테스트·AI 도구가 돌리는 빌드)에는 이 변수가 없어서 파일을
     * 아예 열지 않고 서명 없이 빌드된다. 서명 빌드는 android/build-signed.bat 로만 한다.
     *
     * signing.properties 형식
     *   storeFile=D:/AppCompany/keys/upload-key.jks   (역슬래시 대신 / 를 쓴다)
     *   storePassword=...
     *   keyAlias=upload
     *   keyPassword=...
     *
     * Play App Signing 을 쓰면 이 키는 "업로드 키" 다. 잃어버려도 Play Console 에서
     * 재설정할 수 있지만 번거로우니 백업해 둔다.
     */
    val signingFile = System.getenv("FINDGLASSES_SIGNING_FILE")?.let { file(it) }?.takeIf { it.exists() }
    signingConfigs {
        create("release") {
            if (signingFile != null) {
                val p = Properties().apply { signingFile.inputStream().use { load(it) } }
                storeFile = file(p.getProperty("storeFile"))
                storePassword = p.getProperty("storePassword")
                keyAlias = p.getProperty("keyAlias")
                keyPassword = p.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (signingFile != null) {
                signingConfig = signingConfigs.getByName("release")
            }
            val appId = localProps.getProperty("admob.appId")
            if (appId == null) {
                logger.warn("local.properties 에 admob.* 가 없어 release 도 테스트 광고 ID 로 빌드한다")
            }
            manifestPlaceholders["admobAppId"] = appId ?: AdmobTest.APP
            buildConfigField("String", "ADMOB_BANNER",
                "\"${localProps.getProperty("admob.bannerId") ?: AdmobTest.BANNER}\"")
            buildConfigField("String", "ADMOB_INTERSTITIAL",
                "\"${localProps.getProperty("admob.interstitialId") ?: AdmobTest.INTERSTITIAL}\"")
        }
        debug {
            isMinifyEnabled = false
            manifestPlaceholders["admobAppId"] = AdmobTest.APP
            buildConfigField("String", "ADMOB_BANNER", "\"${AdmobTest.BANNER}\"")
            buildConfigField("String", "ADMOB_INTERSTITIAL", "\"${AdmobTest.INTERSTITIAL}\"")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        viewBinding = true
        buildConfig = true
    }
}

configurations.all {
    // camera-core 는 guava 의 빈 스텁(listenablefuture)을 끌어오고, 광고 SDK 는
    // 실제 guava 를 끌어온다. 둘이 부딪혀 ListenableFuture 를 못 찾는다.
    // 스텁을 빼고 실제 guava 하나만 쓴다.
    exclude(group = "com.google.guava", module = "listenablefuture")
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.viewpager2:viewpager2:1.1.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    val camerax = "1.3.4"
    implementation("androidx.camera:camera-core:$camerax")
    implementation("androidx.camera:camera-camera2:$camerax")
    implementation("androidx.camera:camera-lifecycle:$camerax")
    implementation("androidx.camera:camera-view:$camerax")

    // ONNX Runtime — NNAPI 실행 프로바이더 포함 빌드
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.19.2")

    // 광고 (기획서 14절). 실제 ID 는 local.properties — 위 설명 참고.
    implementation("com.google.android.gms:play-services-ads:23.3.0")
    // 광고 동의 (유럽 GDPR 등). AdMob 이 요구한다.
    implementation("com.google.android.ump:user-messaging-platform:4.0.0")
    // 광고 제거 결제. 2026-08-31 부터 Play 에 올리는 앱은 Billing Library 8 이상이어야 한다.
    implementation("com.android.billingclient:billing:9.1.0")
    implementation("com.google.guava:guava:33.3.1-android")
}
