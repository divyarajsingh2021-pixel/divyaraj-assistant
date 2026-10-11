#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define AppName "Divyaraj Assistant"
#define AppExe "DivyarajAssistant.exe"
#define ProjectRoot AddBackslash(SourcePath) + ".."

[Setup]
AppId={{C16F96D8-C6B0-4A31-AF97-4D16D438C123}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Divyaraj Singh
DefaultDirName={autopf}\Divyaraj Assistant
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile={#ProjectRoot}\packaging\divyaraj.ico
OutputDir={#ProjectRoot}\dist\installer
OutputBaseFilename=DivyarajSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
Uninstallable=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#ProjectRoot}\dist\DivyarajAssistant\*"; \
    DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; \
    Parameters: "--gui"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; \
    Parameters: "--gui"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Parameters: "--gui"; WorkingDir: "{app}"; \
    Description: "Launch {#AppName}"; \
    Flags: postinstall nowait skipifsilent runasoriginaluser

[UninstallDelete]
Type: files; Name: "{userstartup}\Divyaraj Assistant.cmd"
