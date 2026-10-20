# CarbonDelta'yı bu bilgisayara kurar: dist\CarbonDelta -> %LOCALAPPDATA%\Programs\CarbonDelta
# Masaüstüne ve Başlat menüsüne kısayol oluşturur. Önce build.bat çalıştırılmış olmalı.
$ErrorActionPreference = "Stop"
$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $root "dist\CarbonDelta"
$target = Join-Path $env:LOCALAPPDATA "Programs\CarbonDelta"
$exe    = Join-Path $target "CarbonDelta.exe"

if (-not (Test-Path (Join-Path $source "CarbonDelta.exe"))) {
    Write-Host "dist\CarbonDelta\CarbonDelta.exe bulunamadı. Önce build.bat çalıştırın." -ForegroundColor Red
    exit 1
}
if (Get-Process -Name CarbonDelta -ErrorAction SilentlyContinue) {
    Write-Host "CarbonDelta şu an açık. Lütfen uygulamayı kapatıp tekrar deneyin." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force $target | Out-Null
# .env hariç her şeyi eşitle (eski sürüm dosyaları silinir).
robocopy $source $target /MIR /XF .env /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Host "Kopyalama başarısız (robocopy $LASTEXITCODE)." -ForegroundColor Red; exit 1 }

# AI anahtarı: proje kökündeki .env kurulum klasörüne kopyalanır (yalnızca bu bilgisayarda kalır).
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) { Copy-Item $envFile (Join-Path $target ".env") -Force; $ai = "açık (.env kopyalandı)" }
else { $ai = "kapalı (.env yok)" }

$shell = New-Object -ComObject WScript.Shell
function New-Shortcut([string]$path) {
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath = $exe
    $lnk.WorkingDirectory = $target
    $lnk.IconLocation = "$exe,0"
    $lnk.Description = "CarbonDelta — Emisyon Potansiyeli Karar Destek"
    $lnk.Save()
}
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "CarbonDelta.lnk"
New-Shortcut (Join-Path $desktop "CarbonDelta.lnk")
New-Shortcut $startMenu

Write-Host ""
Write-Host "CarbonDelta kuruldu." -ForegroundColor Green
Write-Host "  Klasör   : $target"
Write-Host "  Kısayol  : Masaüstü ve Başlat menüsü"
Write-Host "  AI       : $ai"
