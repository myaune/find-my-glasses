# Phase 0 환경 변수 — 캐시를 전부 D 드라이브로 보내고 Avast TLS 가로채기를 우회한다.
# 사용법:  . .\env.ps1   (점 찍고 실행 = dot-source)
$cache  = 'D:\AppCompany\.cache'
$bundle = "$cache\certs\win-ca-bundle.pem"

$env:HF_HOME               = "$cache\hf"
$env:TORCH_HOME            = "$cache\torch"
$env:UV_CACHE_DIR          = "$cache\uv"
$env:UV_PYTHON_INSTALL_DIR = "$cache\uv-python"
$env:UV_SYSTEM_CERTS       = '1'
$env:SSL_CERT_FILE         = $bundle
$env:REQUESTS_CA_BUNDLE    = $bundle
$env:CURL_CA_BUNDLE        = $bundle

if ($env:Path -notlike '*\.local\bin*') {
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}
