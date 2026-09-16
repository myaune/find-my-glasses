# Phase 1 안드로이드 빌드 환경.
# 사용법:  . .\env.ps1   (점 찍고 실행 = dot-source)
#
# 이 머신 고유의 두 가지를 처리한다.
#  - C 가 512GB SSD 라 Gradle 캐시를 D 로 보낸다
#  - Avast Web Shield 가 HTTPS 를 재서명해서, Java 자체 truststore 로는
#    Maven/Google 저장소 접속이 실패한다. Avast 루트를 넣은 복사본을 쓴다
$cache = 'D:\AppCompany\.cache'

$env:JAVA_HOME         = 'D:\Android\AndroidStudio\jbr'
$env:ANDROID_HOME      = "$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT  = $env:ANDROID_HOME
$env:GRADLE_USER_HOME  = "$cache\gradle"
$env:JAVA_TOOL_OPTIONS = "-Djavax.net.ssl.trustStore=$cache\certs\jdk-cacerts -Djavax.net.ssl.trustStorePassword=changeit"

$env:Path = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$cache\gradle-dist\gradle-8.9\bin;$env:Path"
