[Setup]
AppName=UltraWater Client
AppVersion=2.0.0
AppPublisher=UltraWater
AppPublisherURL=https://kithlicat98-hub.github.io/ultrawater-deploy/
DefaultDirName={autopf}\UltraWater Client
DefaultGroupName=UltraWater Client
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=UltraWater-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
MinVersion=10.0
UninstallDisplayName=UltraWater Client

[Tasks]
Name: "desktop"; Description: "Create a desktop shortcut"; Flags: checked

[Files]
Source: "dist\UltraWater\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\UltraWater Client"; Filename: "{app}\UltraWater.exe"
Name: "{autodesktop}\UltraWater Client";  Filename: "{app}\UltraWater.exe"; Tasks: desktop

[Run]
Filename: "{app}\UltraWater.exe"; Description: "Launch UltraWater Client now"; Flags: nowait postinstall skipifsilent
