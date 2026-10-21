; CarbonDelta kurulum sihirbazı (Inno Setup 6). Üretmek için: kurulum.bat
; Yönetici izni gerekmez; kullanıcı klasörüne kurulur. Kaldırma, kullanıcının geçmişini ve
; eklediği veri paketlerini (%APPDATA%\CarbonDeltaDeneme) silmez.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{9162BD7D-C9BD-4A9D-BF48-CA763EF93AA4}
AppName=CarbonDelta Deneme
AppVersion={#AppVersion}
AppVerName=CarbonDelta Deneme {#AppVersion}
AppPublisher=İsmail Ali ASLAN, Emin Burak ÖZTÜRK
AppContact=ismailaliaslan11@gmail.com
AppComments=Emisyon Potansiyeli Karar Destek
VersionInfoVersion={#AppVersion}
VersionInfoDescription=CarbonDelta Kurulum
DefaultDirName={localappdata}\Programs\CarbonDeltaDeneme
DefaultGroupName=CarbonDelta Deneme
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist_installer
OutputBaseFilename=CarbonDeltaDeneme_Kurulum_{#AppVersion}
SetupIconFile=..\desktop\icon.ico
UninstallDisplayIcon={app}\CarbonDeltaDeneme.exe
UninstallDisplayName=CarbonDelta Deneme {#AppVersion}
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
Source: "..\dist\CarbonDeltaDeneme\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".env"

[Icons]
Name: "{autoprograms}\CarbonDelta Deneme"; Filename: "{app}\CarbonDeltaDeneme.exe"; Comment: "Emisyon Potansiyeli Karar Destek"
Name: "{autodesktop}\CarbonDelta Deneme"; Filename: "{app}\CarbonDeltaDeneme.exe"; Comment: "Emisyon Potansiyeli Karar Destek"; Tasks: desktopicon

[Run]
Filename: "{app}\CarbonDeltaDeneme.exe"; Description: "CarbonDelta Deneme'yi şimdi aç"; Flags: nowait postinstall skipifsilent
