; Benchly - Inno Setup installer script
; Compile with: ISCC.exe installer.iss   (after build_portable.ps1 has produced dist\Benchly.exe)

#define AppName "Benchly"
#define AppVersion "1.6.0"
#define AppPublisher "Benchly"
#define AppExe "Benchly.exe"
#ifndef SourceDir
  #define SourceDir "dist"
#endif

[Setup]
AppId={{B7E62A41-9C1D-4D2E-A9F3-BENCHLY100}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
OutputDir=dist_installer
OutputBaseFilename=Benchly-Setup-{#AppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "{#SourceDir}\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{#AppName} (Administrator)"; Filename: "{app}\{#AppExe}"; Parameters: ""; Comment: "Run elevated for full diagnostics"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
