#ifndef SourceDir
  #error SourceDir must point to the PyInstaller onedir application.
#endif
#ifndef OutputDir
  #error OutputDir must point to the installer artifact directory.
#endif
#ifndef AppVersion
  #define AppVersion "0.9.0"
#endif
#ifndef AppFileVersion
  #define AppFileVersion "0.9.0.0"
#endif
#ifndef OutputBaseName
  #define OutputBaseName "BIMChange-Agent-setup"
#endif

#define AppName "BIMChange-Agent"
#define AppPublisher "BIMChange-Agent contributors"
#define AppExeName "BIMChange-Agent.exe"
#define AppIconName "BIMChange-Agent-" + AppVersion + ".ico"

[Setup]
AppId={{B90303A8-681C-4D53-A53D-18AA7B742C4E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern dynamic
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
SetupIconFile=BIMChange-Agent.ico
UninstallDisplayIcon={app}\{#AppIconName}
UninstallDisplayName={#AppName}
VersionInfoDescription={#AppName} Windows installer
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppFileVersion}
VersionInfoVersion={#AppFileVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "BIMChange-Agent.ico"; DestDir: "{app}"; DestName: "{#AppIconName}"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{autodesktop}\{#AppName}.lnk"
Type: files; Name: "{group}\{#AppName}.lnk"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppIconName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppIconName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
