@echo off
rem Testleri calistirir, EXE'yi uretir ve tek dosyalik kurulum sihirbazini olusturur.
cd /d "%~dp0"
call "%~dp0build.bat" || exit /b 1
for /f %%v in ('.venv\Scripts\python -c "from desktop.version import VERSION; print(VERSION)"') do set VER=%%v
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo Inno Setup bulunamadi. Kurmak icin: winget install JRSoftware.InnoSetup
  exit /b 1
)
"%ISCC%" /Q /DAppVersion=%VER% installer\carbondelta.iss || exit /b 1
echo.
echo Kurulum dosyasi hazir: dist_installer\CarbonDelta_Kurulum_%VER%.exe
