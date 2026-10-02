$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project
$version = python -c "from litmetica3d import __version__; print(__version__)"
if ($LASTEXITCODE -ne 0) { throw "读取版本失败" }
$packageName = "litmetica3d-v$version"
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "测试失败，停止打包" }
$assetArchive = Join-Path $project "litmetica3d/mc_assets/26.2.zip"
if (Test-Path -LiteralPath $assetArchive) {
  Remove-Item -LiteralPath $assetArchive -Force
}
Compress-Archive -Path "litmetica3d/mc_assets/26.2/*" `
  -DestinationPath $assetArchive -CompressionLevel Optimal
python -m PyInstaller --noconfirm --clean "litmetica3d-portable.spec"
if ($LASTEXITCODE -ne 0) { throw "EXE 构建失败" }
New-Item -ItemType Directory -Path "release" -Force | Out-Null
Copy-Item -LiteralPath "README.md","LICENSE","便携版使用说明.txt" -Destination "dist/$packageName" -Force
$releaseNotes = "RELEASE_NOTES_v$version.md"
if (Test-Path -LiteralPath $releaseNotes) {
  Copy-Item -LiteralPath $releaseNotes -Destination "dist/$packageName" -Force
}
Compress-Archive -Path "dist/$packageName" `
  -DestinationPath "release/$packageName-portable.zip" `
  -CompressionLevel Optimal -Force
Write-Host "完成: release/$packageName-portable.zip"
