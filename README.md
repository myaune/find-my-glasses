# Find My Glasses

<img src="docs/release/icon-512.png" alt="Find My Glasses icon" width="128" align="right">

**Took your glasses off and now you can't see where you put them?**
Slowly sweep your phone around the room. When the camera spots your glasses,
a big box, arrows, voice guidance and vibration show you where they are.

Korean name: **내 안경 찾기**

- Everything runs **on the device**. Camera video never leaves the phone.
- No account, no sign-up, no server.
- Designed for people who are *not* wearing their glasses: big markers,
  high-contrast colors (yellow → green as confidence rises), voice and haptics.
- Bonus (experimental): keys / car key, phone and remote control.
- 17 languages.

## Status

| Platform | State |
|---|---|
| Android | 1.0, in Play Console testing |
| iOS | Code written, not yet built (see [`ios/README.md`](ios/README.md)) |

## How it works

1. **Detection** — [YOLO-World v2 small](https://docs.ultralytics.com/models/yolo-world/)
   (open-vocabulary, zero-shot). The prompt `"a pair of eyeglasses"` and a few
   negative words are baked into an ONNX model, so no text encoder runs on the phone.
   Runs with ONNX Runtime at 416 / 512 / 640 px, roughly 0.5–1.5 FPS on a mid-range phone.
2. **Tracking between detections** — inference is slow, so the marker is kept in place by
   - gyroscope rotation (the box is re-projected as the phone turns), and
   - normalized cross-correlation patch tracking on a small grayscale frame
     (handles movement and parallax at close range).
3. **Temporal filter** — a detection must repeat before it counts, to avoid flicker.
4. **Display** — a single target, smoothed with a One Euro filter, with an edge arrow
   when it goes off-screen.

No custom training or dataset: only pretrained, zero-shot models.
Model selection and measurements are in [`docs/phase0-results.md`](docs/phase0-results.md).

## Repository layout

```
android/   Android app (Kotlin, CameraX, ONNX Runtime)
ios/       iOS app (SwiftUI, AVFoundation, ONNX Runtime) — not yet built
poc/       Python benchmarks used to choose the model, and export scripts
docs/      Product plan, results, privacy policy, release notes (mostly Korean)
```

## Building (Android)

Requirements: Android Studio (JDK 17), Android SDK 36.

1. **Model file** — not in git (≈50 MB). Export it with
   `poc/scripts/export_android_model.py` and place it at
   `android/app/src/main/assets/yolo-world-s-v2.onnx`.
2. **Debug build**
   ```
   cd android
   ./gradlew :app:assembleDebug
   ```
   Debug builds always use Google's test ad unit IDs.
3. **Release build** — real AdMob IDs go in `android/local.properties`
   (`admob.appId`, `admob.bannerId`, `admob.interstitialId`).
   Signing is read from a file outside the repo only when
   `FINDGLASSES_SIGNING_FILE` is set; see the comment in `android/app/build.gradle.kts`.

## Privacy

The app itself collects nothing. Ads are served by Google AdMob, which collects
the data described in the [privacy policy](https://myaune.github.io/find-my-glasses/privacy/).

## License

The code in this repository is licensed under the [GNU AGPL-3.0](LICENSE).

The bundled model weights (YOLO-World v2, `yolov8s-worldv2`) are distributed by
Ultralytics under AGPL-3.0. The original research and weights are by Tencent AI Lab
(GPL-3.0). All third-party components are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
and in the app's "Open-source licenses" screen.

### Additional permission (AGPL-3.0 section 7)

As an additional permission under section 7 of the GNU AGPL-3.0, the copyright
holders of this repository's own code give you permission to convey the
combined work that links or bundles this code with the Google Mobile Ads SDK,
the Google User Messaging Platform SDK and the Google Play Billing Library
(and their dependencies distributed by Google), without the corresponding
source of those libraries being covered by this License.

This additional permission applies **only to code written by the copyright holders
of this repository**. It does not apply to the model weights distributed by Ultralytics.
