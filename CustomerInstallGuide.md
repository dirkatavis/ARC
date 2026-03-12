# ARC Installation Guide

## For End Users

Use these steps to install ARC on a Windows computer.

## Before You Start

- Windows 10 or Windows 11
- Permission to install software on your workstation
- ARC installer file: `ARC_Setup.exe`

## Install Steps

1. Locate the ARC installer file provided by IT or your project contact.
2. Double-click `ARC_Setup.exe`.
3. If Windows asks for confirmation, choose `Run` or `Yes`.
4. In the ARC Setup Wizard, click `Next`.
5. Accept the default install location unless IT gave you a different instruction.
6. Leave the Start Menu shortcut enabled.
7. Optionally select the desktop shortcut.
8. Click `Install`.
9. Click `Finish`, then launch ARC from Start Menu or desktop shortcut.

Default install location:
- `%LOCALAPPDATA%\\Programs\\ARC`

## First Launch

When ARC starts for the first time:

- The application creates its local data folder automatically.
- The application creates its SQLite database automatically.
- No manual database setup is required by the end user.

## Where ARC Stores Local Files

ARC stores runtime files in the current Windows user profile:

- Database: `%LOCALAPPDATA%\ARC\data\arc_data.db`
- Error log: `%LOCALAPPDATA%\ARC\error_log.txt`

This is intentional and helps avoid Windows permission issues during normal use.

## If Windows Shows a Security Prompt

If Windows SmartScreen or another security prompt appears:

1. Confirm the installer was provided by your organization.
2. Choose `More info` if needed.
3. Choose `Run anyway` only if your organization has approved the installer.

## Troubleshooting

### ARC does not launch after install

- Open the Start Menu and search for `ARC`.
- Launch it from the Start Menu shortcut.
- If it still fails, contact IT and provide the file:
  - `%LOCALAPPDATA%\ARC\error_log.txt`

### ARC opens but does not show expected data

- Confirm you are using the correct installed version.
- Contact IT if a seeded or preloaded database was expected.

### Reinstall ARC

1. Close ARC.
2. Run the newer `ARC_Setup.exe`.
3. Complete the wizard.

The installer is designed to support upgrades without requiring the user to manually remove the previous version first.

## Support

If installation fails, send IT or the project owner:

- A screenshot of the error
- The Windows username
- The file `%LOCALAPPDATA%\ARC\error_log.txt` if it exists