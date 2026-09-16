@echo off
rem Signed release build (AAB) for Play Console upload.
rem Gradle opens the signing file only when FINDGLASSES_SIGNING_FILE is set (only here).
rem The signing file and the full log stay in D:\AppCompany\keys (outside the repo).

set KEYS=D:\AppCompany\keys
set JAVA_HOME=D:\Android\AndroidStudio\jbr
set ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk
set ANDROID_SDK_ROOT=%ANDROID_HOME%
set GRADLE_USER_HOME=D:\AppCompany\.cache\gradle
set JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStore=D:\AppCompany\.cache\certs\jdk-cacerts -Djavax.net.ssl.trustStorePassword=changeit
set PATH=%JAVA_HOME%\bin;%PATH%
set FINDGLASSES_SIGNING_FILE=%KEYS%\signing.properties

if not exist "%FINDGLASSES_SIGNING_FILE%" (
  echo signing file not found in %KEYS%
  set EXITCODE=2
  goto end
)

cd /d "%~dp0"
call .\gradlew.bat :app:clean :app:bundleRelease --console=plain > "%KEYS%\build-signed.log" 2>&1
set EXITCODE=%ERRORLEVEL%

if "%EXITCODE%"=="0" (
  echo BUILD OK
  echo %~dp0app\build\outputs\bundle\release\app-release.aab
) else (
  echo BUILD FAILED - see log in %KEYS%
)

:end
if not "%1"=="nopause" pause
exit /b %EXITCODE%
