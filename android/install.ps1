# Phase 1 측정 앱 설치 + 모델 밀어넣기.
#
#   .\install.ps1              빌드 → 설치 → 모델 push → 실행
#   .\install.ps1 -SkipBuild   이미 빌드된 APK 로
#   .\install.ps1 -Release     release 빌드로 (레이턴시 최종 측정용)
param(
    [switch]$SkipBuild,
    [switch]$Release,
    [switch]$SkipModel
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
. .\env.ps1

$variant  = if ($Release) { 'release' } else { 'debug' }
$taskName = if ($Release) { ':app:assembleRelease' } else { ':app:assembleDebug' }
$apk      = "app\build\outputs\apk\$variant\app-$variant.apk"
$pkg      = 'com.myaune.findglasses'
$remote   = "/sdcard/Android/data/$pkg/files"
$model    = "..\runs\0b\gdino-tiny-eyeglasses-fp16-iofp32.onnx"

# --- 기기 확인 -------------------------------------------------------------
$devices = (adb devices) | Select-Object -Skip 1 | Where-Object { $_ -match '\tdevice$' }
if (-not $devices) {
    Write-Host "기기가 안 보입니다." -ForegroundColor Red
    Write-Host "  1. USB 로 연결"
    Write-Host "  2. 설정 - 휴대전화 정보 - MIUI 버전 7번 연타 (개발자 옵션)"
    Write-Host "  3. 개발자 옵션 - USB 디버깅 켜기"
    Write-Host "  4. 폰에 뜨는 'USB 디버깅 허용' 승인"
    exit 1
}
Write-Host "기기: $($devices -join ', ')" -ForegroundColor Green

# --- 빌드 -----------------------------------------------------------------
if (-not $SkipBuild) {
    Write-Host "`n빌드 ($variant) ..." -ForegroundColor Cyan
    .\gradlew.bat $taskName --console=plain
    if ($LASTEXITCODE -ne 0) { Write-Host "빌드 실패" -ForegroundColor Red; exit 1 }
}
if (-not (Test-Path $apk)) { Write-Host "APK 없음: $apk" -ForegroundColor Red; exit 1 }
"APK {0:N1} MB" -f ((Get-Item $apk).Length / 1MB)

# --- 설치 -----------------------------------------------------------------
Write-Host "`n설치 ..." -ForegroundColor Cyan
adb install -r $apk
if ($LASTEXITCODE -ne 0) { Write-Host "설치 실패" -ForegroundColor Red; exit 1 }

# --- 모델 -----------------------------------------------------------------
# APK 에 넣지 않는다. 124.6MB 라 빌드/설치가 느려지고, 측정 단계에서는
# 해상도를 바꿔가며 모델을 자주 교체하기 때문이다. 출시 앱은 번들한다.
if (-not $SkipModel) {
    if (-not (Test-Path $model)) {
        Write-Host "모델이 없습니다: $model" -ForegroundColor Red
        Write-Host "  cd ..\poc; . .\env.ps1"
        Write-Host "  uv run python scripts\export_onnx.py --prompt eyeglasses --out ..\runs\0b"
        Write-Host "  uv run python scripts\onnx_fp16.py --run ..\runs\0b --keep-io-fp32"
        exit 1
    }
    $name = Split-Path $model -Leaf
    $size = (Get-Item $model).Length
    $existing = (adb shell "ls -l $remote/$name 2>/dev/null" | Out-String)
    if ($existing -match "\s$size\s") {
        Write-Host "`n모델 이미 최신 — 건너뜀" -ForegroundColor DarkGray
    } else {
        Write-Host ("`n모델 push ({0:N1} MB) — 1~2분 걸립니다 ..." -f ($size / 1MB)) -ForegroundColor Cyan
        adb shell "mkdir -p $remote"
        adb push $model "$remote/"
        if ($LASTEXITCODE -ne 0) { Write-Host "push 실패" -ForegroundColor Red; exit 1 }
    }
}

# --- 실행 -----------------------------------------------------------------
Write-Host "`n실행 ..." -ForegroundColor Cyan
adb shell monkey -p $pkg -c android.intent.category.LAUNCHER 1 | Out-Null

Write-Host "`n완료." -ForegroundColor Green
Write-Host "로그 가져오기:  adb pull $remote/logs ..\runs\phase1"
