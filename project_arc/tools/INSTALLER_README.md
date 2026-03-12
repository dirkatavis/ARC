# ARC Windows Installer Build

This flow creates a customer-ready `ARC_Setup.exe` for ARC.

## Prerequisites (builder machine)
- Windows 10/11
- Python virtual environment at repository root (`.venv`)
- Inno Setup 6 installed and `iscc.exe` available on PATH

## Build command
From repository root:

```powershell
powershell -ExecutionPolicy Bypass -File project_arc/tools/build_setup.ps1 -Version 1.0.0 -Clean
```

## Output artifact
- `project_arc/dist/installer/ARC_Setup.exe`

## End-user experience
1. User runs `ARC_Setup.exe`
2. Wizard installs ARC into the current user's local programs folder
3. Start Menu shortcut is created
4. Optional desktop shortcut can be selected
5. User launches ARC from Start Menu or desktop shortcut

## Runtime storage behavior
- Database: `%LOCALAPPDATA%\ARC\data\arc_data.db`
- Error log: `%LOCALAPPDATA%\ARC\error_log.txt`

This avoids write-permission issues in Program Files and supports reliable upgrades.
