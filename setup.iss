; Inno Setup 6 script for NEON GRID.
; Built automatically by `python build.py`, or manually:
;   ISCC.exe /DAppVersion=1.0.0 setup.iss
; Expects the PyInstaller folder build in dist\NeonGrid\.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "NEON GRID"
#define AppExe "NeonGrid.exe"

[Setup]
AppId={{6B0C2F7E-9E2B-4D55-9A3C-4E0D2B7F1A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=NEON GRID
DefaultDirName={autopf}\NeonGrid
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=NeonGrid-Setup-{#AppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; per-user install by default (no admin prompt); user may choose all users
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; updates reuse the existing folder/options and close a running game first
DisableDirPage=auto
DisableReadyPage=no
UsePreviousAppDir=yes
UsePreviousTasks=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "hebrew"; MessagesFile: "compiler:Languages\Hebrew.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "firewall"; Description: "{cm:FirewallTask}"; GroupDescription: "{cm:NetworkGroup}"

[Files]
Source: "dist\NeonGrid\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

; Player data (settings, profile, stats, logs) lives in %APPDATA%\NeonGrid and is
; intentionally kept on uninstall so progress survives reinstalls.

[CustomMessages]
english.AlreadyUpdate=%1 %2 is already installed.%n%nDo you want to update it to version %3?%n%nYour progress and settings will be kept.
english.AlreadySame=%1 %2 is already installed.%n%nDo you want to reinstall (repair) it?%n%nYour progress and settings will be kept.
english.AlreadyNewer=A newer version of %1 (%2) is already installed.%n%nDo you want to replace it with the older version %3?
english.UpdateTitle=Update %1
english.NetworkGroup=Multiplayer:
english.FirewallTask=Allow NEON GRID through Windows Firewall (needed to host or find LAN games; asks for admin permission)
hebrew.AlreadyUpdate=%1 %2 כבר מותקן.%n%nהאם לעדכן לגרסה %3?%n%nההתקדמות וההגדרות שלך יישמרו.
hebrew.AlreadySame=%1 %2 כבר מותקן.%n%nהאם להתקין מחדש (תיקון)?%n%nההתקדמות וההגדרות שלך יישמרו.
hebrew.AlreadyNewer=גרסה חדשה יותר של %1 (%2) כבר מותקנת.%n%nהאם להחליף אותה בגרסה הישנה %3?
hebrew.UpdateTitle=עדכון %1
hebrew.NetworkGroup=מרובה משתתפים:
hebrew.FirewallTask=אפשר ל-NEON GRID לעבור את חומת האש של Windows (נדרש לאירוח או מציאת משחקים ברשת; מבקש הרשאת מנהל)

[Code]
const
  UninstKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6B0C2F7E-9E2B-4D55-9A3C-4E0D2B7F1A11}_is1';

var
  InstalledVersion: String;

{ Finds an existing installation (per-user or all-users) and returns its version. }
function GetInstalledVersion(): String;
begin
  Result := '';
  if not RegQueryStringValue(HKCU, UninstKey, 'DisplayVersion', Result) then
    if not RegQueryStringValue(HKLM64, UninstKey, 'DisplayVersion', Result) then
      if not RegQueryStringValue(HKLM32, UninstKey, 'DisplayVersion', Result) then
        Result := '';
end;

{ Compares dotted versions: -1 if A < B, 0 if equal, 1 if A > B. }
function CompareVersions(A, B: String): Integer;
var
  PA, PB, NA, NB: Integer;
begin
  Result := 0;
  while (Result = 0) and ((A <> '') or (B <> '')) do
  begin
    PA := Pos('.', A);
    PB := Pos('.', B);
    if PA = 0 then begin NA := StrToIntDef(A, 0); A := ''; end
    else begin NA := StrToIntDef(Copy(A, 1, PA - 1), 0); Delete(A, 1, PA); end;
    if PB = 0 then begin NB := StrToIntDef(B, 0); B := ''; end
    else begin NB := StrToIntDef(Copy(B, 1, PB - 1), 0); Delete(B, 1, PB); end;
    if NA < NB then Result := -1
    else if NA > NB then Result := 1;
  end;
end;

{ Runs before the wizard: if NEON GRID is already installed, ask what to do. }
function InitializeSetup(): Boolean;
var
  Msg: String;
  Cmp: Integer;
begin
  Result := True;
  InstalledVersion := GetInstalledVersion();
  if InstalledVersion = '' then
    Exit;
  Cmp := CompareVersions(InstalledVersion, '{#AppVersion}');
  if Cmp < 0 then
    Msg := FmtMessage(CustomMessage('AlreadyUpdate'), ['{#AppName}', InstalledVersion, '{#AppVersion}'])
  else if Cmp = 0 then
    Msg := FmtMessage(CustomMessage('AlreadySame'), ['{#AppName}', InstalledVersion, '{#AppVersion}'])
  else
    Msg := FmtMessage(CustomMessage('AlreadyNewer'), ['{#AppName}', InstalledVersion, '{#AppVersion}']);
  Log('Existing install detected: ' + InstalledVersion + ' -> ' + '{#AppVersion}');
  Log('Prompt: ' + Msg);
  { silent installs (/SILENT, /VERYSILENT) update without asking }
  if not WizardSilent() then
    Result := MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES;
end;

{ Windows Firewall: one program rule (TCP + UDP) for the game exe, added through
  an elevated netsh so a per-user install can still open the ports. }
procedure RunElevatedNetsh(Params: String);
var
  Code: Integer;
begin
  if not ShellExec('runas', ExpandConstant('{sys}\netsh.exe'), Params, '', SW_HIDE,
                   ewWaitUntilTerminated, Code) then
    Log('netsh could not be started: ' + SysErrorMessage(Code))
  else
    Log('netsh ' + Params + ' -> ' + IntToStr(Code));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Exe: String;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('firewall') then
  begin
    Exe := ExpandConstant('{app}\{#AppExe}');
    RunElevatedNetsh('advfirewall firewall delete rule name="NEON GRID"');
    RunElevatedNetsh('advfirewall firewall add rule name="NEON GRID" dir=in action=allow ' +
                     'program="' + Exe + '" enable=yes profile=private,public,domain');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RunElevatedNetsh('advfirewall firewall delete rule name="NEON GRID"');
end;

{ Show "Update NEON GRID" as the wizard title when updating. }
procedure InitializeWizard();
begin
  if InstalledVersion <> '' then
    WizardForm.Caption := FmtMessage(CustomMessage('UpdateTitle'), ['{#AppName}']);
end;
