param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw '创建 Python 虚拟环境失败。' }
    }
    & .\.venv\Scripts\python.exe -m pip install -r requirements-winui.txt
    if ($LASTEXITCODE -ne 0) { throw '安装转换引擎依赖失败。' }
    & dotnet build frontend/Litmetica3D.WinUI/Litmetica3D.WinUI.csproj -c Release -p:Platform=x64
    if ($LASTEXITCODE -ne 0) { throw 'WinUI 构建失败。' }
    Write-Host '准备完成。运行 .\run_winui.ps1 启动。'
} finally { Pop-Location }
