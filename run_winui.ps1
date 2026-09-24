param([switch]$Build)
$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot 'frontend\Litmetica3D.WinUI\Litmetica3D.WinUI.csproj'
$exe = Join-Path $PSScriptRoot 'frontend\Litmetica3D.WinUI\bin\x64\Release\net10.0-windows10.0.26100.0\win-x64\Litmetica3D.WinUI.exe'
if ($Build -or -not (Test-Path -LiteralPath $exe)) {
    & dotnet build $project -c Release -p:Platform=x64
    if ($LASTEXITCODE -ne 0) { throw 'WinUI 构建失败。请先运行 setup_winui.ps1。' }
}
Start-Process -FilePath $exe -WorkingDirectory $PSScriptRoot
