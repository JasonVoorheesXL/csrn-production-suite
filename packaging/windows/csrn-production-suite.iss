; CSRN Production Suite Windows installer foundation
; Compile with Inno Setup after producing dist-windows\CSRNProductionSuite.
;
; Round 15G changes:
;   * launches the pywebview desktop shell exe (csrn_desktop.py, frozen as
;     CSRNProductionSuite.exe) -- no .ps1 / .bat chain;
;   * desktop + Start-Menu shortcuts for the shell (desktop opt-in);
;   * inbound firewall rules for :5050 (control surface + phone/tablet/iPad
;     LAN access) and :5051 (isolated media server) so there is no
;     per-launch Windows Firewall prompt; removed on uninstall;
;   * optional bundled Evergreen WebView2 bootstrapper for older Win10
;     (pywebview needs the WebView2 runtime; it is already present on
;     Win11 and current Win10);
;   * larger payload note -- the bundle now carries the whisper small.en
;     model + Playwright's Chromium (~1 GB); lzma2 + solid compression.
;
; Code signing is deliberately deferred -- SignTool configuration is
; intentionally external. Unsigned test builds must not be represented as
; signed production releases.

#define MyAppName "CSRN Production Suite"
#define MyAppPublisher "PossumFrog"
#define MyAppExeName "CSRNProductionSuite.exe"
; Pass /DMyAppVersion=... to ISCC from VERSION.txt at build time.
#ifndef MyAppVersion
  #define MyAppVersion "1.13.0-alpha.8f"
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
; Optional: drop MicrosoftEdgeWebview2Setup.exe next to this .iss to bundle
; the WebView2 bootstrapper for older Win10 machines.
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: dontcopy skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--installed"; WorkingDir: "{app}"
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--installed"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--installed"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
; WebView2 runtime -- only runs if the bootstrapper was bundled; the
; installer silently no-ops when WebView2 is already present.
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; Flags: skipifdoesntexist waituntilterminated; StatusMsg: "Installing the Microsoft WebView2 runtime..."
; Firewall: allow inbound CSRN traffic so phones/tablets/iPads on the LAN
; and OBS on another machine can reach the control surface + overlays, with
; no per-launch Windows Firewall prompt.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""CSRN Production Suite (5050)"" dir=in action=allow protocol=TCP localport=5050"; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""CSRN Production Suite media (5051)"" dir=in action=allow protocol=TCP localport=5051"; Flags: runhidden
Filename: "{app}\{#MyAppExeName}"; Parameters: "--installed"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""CSRN Production Suite (5050)"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""CSRN Production Suite media (5051)"""; Flags: runhidden

[UninstallDelete]
; Application binaries are removable. Customer runtime data under
; {localappdata}\PossumFrog\CSRN Production Suite is intentionally preserved.
Type: filesandordirs; Name: "{app}"
