; CSRN Production Suite Windows installer foundation
; Compile with Inno Setup after producing dist-windows\CSRNProductionSuite.

#define MyAppName "CSRN Production Suite"
#define MyAppPublisher "PossumFrog"
#define MyAppExeName "CSRNProductionSuite.exe"
#ifndef MyAppVersion
  #define MyAppVersion "1.13.0-alpha.6g"
#endif

[Setup]
AppId={{B2B122B3-49B0-4E14-A8FC-0EEB1CF169C7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\PossumFrog\CSRN Production Suite
DefaultGroupName=PossumFrog
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputDir=..\..\dist-installer
OutputBaseFilename=CSRN-Production-Suite-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}
ChangesEnvironment=no

[Files]
Source: "..\..\dist-windows\CSRNProductionSuite\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--installed"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--installed"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--installed"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Application binaries are removable. Customer runtime data under
; {localappdata}\PossumFrog\CSRN Production Suite is intentionally preserved.
Type: filesandordirs; Name: "{app}"
