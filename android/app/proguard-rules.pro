# R8 (코드 축소·난독화) 보존 규칙.
#
# ONNX Runtime 은 네이티브 코드(JNI)가 자바 클래스·필드·메서드를 이름으로 찾는다.
# 이름이 바뀌거나 지워지면 추론이 실행 중에 깨진다. AAR 에 보존 규칙이 들어 있지 않아서
# 여기서 직접 지킨다.
-keep class ai.onnxruntime.** { *; }
-keepclasseswithmembernames class * {
    native <methods>;
}

# 스택 트레이스에서 줄 번호를 읽을 수 있게 (Play Console 이 mapping 으로 되돌린다)
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
