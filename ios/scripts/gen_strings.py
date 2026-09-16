"""Android strings.xml (17개 언어) → iOS String Catalog 두 개를 만든다.

  FindGlasses/Resources/Localizable.xcstrings   앱 안 문구 (키 = Android 이름)
  FindGlasses/Resources/InfoPlist.xcstrings     앱 이름, 카메라 권한 문구

문구의 원천은 Android 쪽이다. 문구를 고치면 Android 를 고치고 이 스크립트를 다시 돌린다.
표준 라이브러리만 쓴다.

    python ios/scripts/gen_strings.py
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "android" / "app" / "src" / "main" / "res"
OUT = ROOT / "ios" / "FindGlasses" / "Resources"

# Android 폴더 → iOS 언어 코드
LANGS = {
    "values": "en",
    "values-ko": "ko",
    "values-ja": "ja",
    "values-es": "es",
    "values-zh-rCN": "zh-Hans",
    "values-zh-rTW": "zh-Hant",
    "values-pt": "pt-BR",
    "values-fr": "fr",
    "values-de": "de",
    "values-it": "it",
    "values-ru": "ru",
    "values-tr": "tr",
    "values-ar": "ar",
    "values-hi": "hi",
    "values-in": "id",
    "values-vi": "vi",
    "values-th": "th",
}

# 카메라 권한 문구 (iOS 전용이라 Android 에 없다)
CAMERA = {
    "en": "The camera is used to find your glasses. Video is processed only on this device and never leaves it.",
    "ko": "안경을 찾기 위해 카메라를 사용해요. 영상은 기기 안에서만 처리되고 밖으로 나가지 않아요.",
    "ja": "メガネを探すためにカメラを使います。映像はこの端末の中だけで処理され、外部に送られません。",
    "es": "La cámara se usa para encontrar tus gafas. El vídeo se procesa solo en este dispositivo y nunca sale de él.",
    "zh-Hans": "使用相机来寻找你的眼镜。画面只在本机处理，不会上传。",
    "zh-Hant": "使用相機來尋找你的眼鏡。畫面只在本機處理，不會上傳。",
    "pt-BR": "A câmera é usada para achar seus óculos. O vídeo é processado só neste aparelho e nunca sai dele.",
    "fr": "La caméra sert à trouver vos lunettes. La vidéo est traitée uniquement sur cet appareil et n’en sort jamais.",
    "de": "Die Kamera wird genutzt, um deine Brille zu finden. Das Video wird nur auf diesem Gerät verarbeitet und verlässt es nie.",
    "it": "La fotocamera serve a trovare i tuoi occhiali. Il video viene elaborato solo su questo dispositivo e non esce mai.",
    "ru": "Камера нужна, чтобы найти очки. Видео обрабатывается только на этом устройстве и никуда не передаётся.",
    "tr": "Kamera gözlüğünü bulmak için kullanılır. Görüntü yalnızca bu cihazda işlenir ve dışarı gönderilmez.",
    "ar": "تُستخدم الكاميرا للعثور على نظارتك. تتم معالجة الفيديو على هذا الجهاز فقط ولا يغادره أبداً.",
    "hi": "आपका चश्मा ढूंढने के लिए कैमरा इस्तेमाल होता है। वीडियो सिर्फ़ इसी डिवाइस पर प्रोसेस होता है और बाहर नहीं जाता।",
    "id": "Kamera dipakai untuk mencari kacamatamu. Video hanya diproses di perangkat ini dan tidak pernah dikirim keluar.",
    "vi": "Camera được dùng để tìm kính của bạn. Video chỉ được xử lý trên thiết bị này và không bao giờ gửi ra ngoài.",
    "th": "ใช้กล้องเพื่อหาแว่นของคุณ วิดีโอประมวลผลในเครื่องนี้เท่านั้นและไม่ถูกส่งออกไป",
}

SKIP = {"tts_locale"}  # 코드가 직접 쓰지만 번역 대상은 아니다 → 아래에서 따로 넣는다


def android_to_ios(s: str) -> str:
    s = s.replace("\\'", "'").replace('\\"', '"').replace("\\n", "\n")
    # %1$s → %1$@ (위치 인자 유지)
    s = re.sub(r"%(\d+)\$s", r"%\1$@", s)
    return s


def unit(value: str) -> dict:
    return {"stringUnit": {"state": "translated", "value": value}}


def main() -> None:
    table: dict[str, dict[str, str]] = {}
    for folder, lang in LANGS.items():
        tree = ET.parse(RES / folder / "strings.xml")
        for el in tree.getroot().findall("string"):
            name = el.get("name")
            text = "".join(el.itertext())
            table.setdefault(name, {})[lang] = android_to_ios(text)

    strings = {}
    for key in sorted(table):
        locs = {lang: unit(v) for lang, v in table[key].items()}
        entry = {"localizations": locs}
        if key in SKIP:
            entry["shouldTranslate"] = False
        strings[key] = entry

    catalog = {"sourceLanguage": "en", "strings": strings, "version": "1.0"}
    (OUT / "Localizable.xcstrings").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    info = {
        "sourceLanguage": "en",
        "strings": {
            "CFBundleDisplayName": {"localizations": {
                lang: unit(v) for lang, v in table["app_name"].items()}},
            "NSCameraUsageDescription": {"localizations": {
                lang: unit(v) for lang, v in CAMERA.items()}},
        },
        "version": "1.0",
    }
    (OUT / "InfoPlist.xcstrings").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(strings)} keys × {len(LANGS)} languages")


if __name__ == "__main__":
    main()
