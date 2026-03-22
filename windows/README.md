# Notchi for Windows

This folder contains the Windows desktop release of Notchi.

## Features

- Auto-installs a Claude Code hook on startup
- Receives live Claude Code events over `127.0.0.1:8765`
- Shows one animated mascot per active Claude Code session
- Supports automatic state switching:
  - `idle`
  - `working`
  - `waiting`
  - `compacting`
  - `sleeping`
- Supports automatic emotion switching:
  - `neutral`
  - `happy`
  - `sad`
  - `sob`
- Supports compact hide mode and expandable detail mode

## Run

```powershell
git clone https://github.com/AptatoX/notchi-for-windows.git
cd notchi-for-windows/windows
python app.py
```

## Interaction

- Launch: starts in hide mode
- Double-click a mascot: toggle between hide and detail for that session
- Multiple Claude Code sessions: each session gets its own mascot

## Notes

- The Windows app is self-contained and does not depend on the original Xcode project.
- It uses PowerShell hooks and a local TCP listener instead of the macOS Unix socket flow.
- Bundled sprite sheets live under `windows/assets/sprites`.

## Attribution

- Based on [sk-ruban/notchi](https://github.com/sk-ruban/notchi)
- Original sprite assets and concept remain credited to the upstream project and its authors
