$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "测试失败，停止打包" }
$assetArchive = Join-Path $project "litmetica3d/mc_assets/26.2.zip"
if (Test-Path -LiteralPath $assetArchive) {
  Remove-Item -LiteralPath $assetArchive -Force
}
Compress-Archive -Path "litmetica3d/mc_assets/26.2/*" `
  -DestinationPath $assetArchive -CompressionLevel Optimal
python -m PyInstaller --noconfirm --clean "litmetica3d-v0.5.1-portable.spec"
if ($LASTEXITCODE -ne 0) { throw "EXE 构建失败" }
New-Item -ItemType Directory -Path "release" -Force | Out-Null
Copy-Item -LiteralPath "README.md","LICENSE","便携版使用说明.txt","RELEASE_NOTES_v0.5.1.md" -Destination "dist/litmetica3d-v0.5.1" -Force
Compress-Archive -Path "dist/litmetica3d-v0.5.1" `
  -DestinationPath "release/litmetica3d-v0.5.1-portable.zip" `
  -CompressionLevel Optimal -Force
Write-Host "完成: release/litmetica3d-v0.5.1-portable.zip"
