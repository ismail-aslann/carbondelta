; CarbonDelta kurulum sihirbazı (Inno Setup 6). Üretmek için: kurulum.bat
; Yönetici izni gerekmez; kullanıcı klasörüne kurulur. Kaldırma, kullanıcının geçmişini ve
; eklediği veri paketlerini (%APPDATA%\CarbonDelta) silmez.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{B4D99CA7-94B3-4D3F-84DD-39805510DCE0}
AppName=CarbonDelta
AppVersion={#AppVersion}
AppVerName=CarbonDelta {#AppVersion}
AppPublisher=İsmail Ali ASLAN, Emin Burak ÖZTÜRK
AppContact=ismailaliaslan11@gmail.com
AppComments=Emisyon Potansiyeli Karar Destek
VersionInfoVersion={#AppVersion}
VersionInfoDescription=CarbonDelta Kurulum
DefaultDirName={localappdata}\Programs\CarbonDelta
DefaultGroupName=CarbonDelta
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist_installer
OutputBaseFilename=CarbonDelta_Kurulum_{#AppVersion}
SetupIconFile=..\desktop\icon.ico
UninstallDisplayIcon={app}\CarbonDelta.exe
UninstallDisplayName=CarbonDelta {#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Kısayollar:"

[InstallDelete]
; Eski sürümün dosyaları kalmasın
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\CarbonDelta\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".env"

[Icons]
Name: "{autoprograms}\CarbonDelta"; Filename: "{app}\CarbonDelta.exe"; Comment: "Emisyon Potansiyeli Karar Destek"
Name: "{autodesktop}\CarbonDelta"; Filename: "{app}\CarbonDelta.exe"; Comment: "Emisyon Potansiyeli Karar Destek"; Tasks: desktopicon

[Run]
Filename: "{app}\CarbonDelta.exe"; Description: "CarbonDelta'yı şimdi aç"; Flags: nowait postinstall skipifsilent
