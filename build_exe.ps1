$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project
python -m pytest -q
$assetArchive = Join-Path $project "litmetica3d/mc_assets/26.2.zip"
if (Test-Path -LiteralPath $assetArchive) {
  Remove-Item -LiteralPath $assetArchive -Force
}
Compress-Archive -Path "litmetica3d/mc_assets/26.2/*" `
  -DestinationPath $assetArchive -CompressionLevel Optimal
python -m PyInstaller --noconfirm --clean "litmetica3d-v0.5.0-portable.spec"
New-Item -ItemType Directory -Path "release" -Force | Out-Null
Copy-Item -LiteralPath "README.md" -Destination "dist/litmetica3d-v0.5.0/README.md" -Force
Copy-Item -LiteralPath "便携版使用说明.txt" -Destination "dist/litmetica3d-v0.5.0/便携版使用说明.txt" -Force
Compress-Archive -Path "dist/litmetica3d-v0.5.0" `
  -DestinationPath "release/litmetica3d-v0.5.0-portable.zip" `
  -CompressionLevel Optimal -Force
Write-Host "完成: release/litmetica3d-v0.5.0-portable.zip"
