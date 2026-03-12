#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

#ifndef ArcDistDir
  #define ArcDistDir "..\\dist\\ARC"
#endif

[Setup]
AppId={{CBEA170A-0D16-4D7B-B444-9D682B2B49A1}
AppName=ARC
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\ARC
DefaultGroupName=ARC
OutputDir=..\dist\installer
OutputBaseFilename=ARC_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
DisableWelcomePage=no
DisableDirPage=no
DisableReadyPage=no
DisableFinishedPage=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#ArcDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\ARC"; Filename: "{app}\ARC.exe"
Name: "{autodesktop}\ARC"; Filename: "{app}\ARC.exe"; Tasks: desktopicon
