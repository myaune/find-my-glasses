# Third-party notices

This app is licensed under the [GNU AGPL-3.0](LICENSE) (see the additional permission in the
[README](README.md#additional-permission-agpl-30-section-7)). It includes or depends on the
components below. The same list, with full license texts, is shown in the app under
**Settings / Tutorial → Open-source licenses**.

Full license texts shipped with the apps:
`android/app/src/main/res/raw/` and `ios/FindGlasses/Resources/Licenses/`.

## Bundled in the app

| Component | Owner | License | Where |
|---|---|---|---|
| YOLO-World v2 small model weights (`yolov8s-worldv2`), exported to ONNX | Ultralytics (original research: Tencent AI Lab CVC, GPL-3.0) | AGPL-3.0 | Android, iOS |
| CLIP text embeddings (computed once at export time, baked into the model) | OpenAI | MIT | Android, iOS |
| ONNX Runtime | Microsoft | MIT | Android, iOS |
| AndroidX — CameraX, AppCompat, Core, Lifecycle, ConstraintLayout, ViewPager2 | The Android Open Source Project | Apache-2.0 | Android |
| Material Components for Android | Google | Apache-2.0 | Android |
| Kotlin standard library, kotlinx.coroutines | JetBrains | Apache-2.0 | Android |
| Guava | Google | Apache-2.0 | Android |
| Google Mobile Ads SDK, User Messaging Platform SDK | Google | Proprietary ([Google Mobile Ads SDK Terms](https://developers.google.com/admob/terms)) — covered by the additional permission | Android, iOS |

## Model weights — corresponding source

The weights are not stored in this repository (≈50 MB). They are the unmodified
`yolov8s-worldv2.pt` published by Ultralytics
(<https://github.com/ultralytics/ultralytics>), with the vocabulary set and exported to ONNX by
[`poc/scripts/export_android_model.py`](poc/scripts/export_android_model.py). Running that script
reproduces the file bundled in the app. No training or fine-tuning was done.

## Used only for development (not distributed in the app)

The Python benchmarks in `poc/` use packages such as `ultralytics` (AGPL-3.0), PyTorch and torchvision
(BSD-3-Clause), Hugging Face `transformers` (Apache-2.0), `onnx` / `onnxruntime` (Apache-2.0 / MIT),
OpenCV (Apache-2.0), CLIP (MIT)
and Pillow (HPND). They are installed from their own sources via `poc/pyproject.toml`
and are not part of the app.

## App assets

The app icon, tutorial illustrations and all other artwork were created for this project and are
covered by the repository license.
