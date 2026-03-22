# Notchi for Windows

A Windows desktop companion inspired by and ported from [sk-ruban/notchi](https://github.com/sk-ruban/notchi), built for Claude Code.

This repository is now a Windows-only release. It keeps the original pixel mascot and sprite sheets, but adapts the app to Windows with a small always-on-top overlay, PowerShell hooks, and local event listening.

## Quick Look

<p align="center">
  <img src="assets/windows-mascots.gif" alt="Animated mascots" width="640">
</p>

Animated preview of `happy`, `sad`, `waiting`, and `sleeping` state transitions.

## What It Does

- Reacts to Claude Code activity in real time
- Shows one sprite per Claude Code session
- Uses bundled Notchi sprite animations adapted from the upstream project
- Switches between `idle`, `working`, `waiting`, `compacting`, and `sleeping`
- Switches emotions between `neutral`, `happy`, `sad`, and `sob`
- Lets you hide to a compact mascot-only view or expand into a detail panel

## Current Status

The Windows port is usable, but it is still not a full 1:1 port of the original macOS app.

Implemented today:

- Windows hook installer for Claude Code
- Local TCP event listener
- Multi-session sprite rendering
- Detail panel with recent prompt, reply, and activity info
- Automatic state and emotion switching
- Bundled sprite-sheet assets for the Windows app

Not ported yet:

- exact notch-shaped macOS UI
- Sparkle-style auto-updates
- exact visual parity with the native Swift app

## Run

```powershell
git clone https://github.com/AptatoX/notchi-for-windows.git
cd notchi-for-windows/windows
python -m pip install -r ../requirements.txt
python app.py
```

On launch, the app starts in hide mode and attempts to install the Claude Code hook automatically.

More Windows-specific notes are in [windows/README.md](windows/README.md).

## Project Structure

- [windows/](windows/README.md): Windows app, hook, and bundled sprite assets
- [scripts/](scripts): helper scripts for Windows media generation and cleanup

## Attribution

This project is based on the original [sk-ruban/notchi](https://github.com/sk-ruban/notchi) project.

Credits to the original authors for:

- the app concept
- sprite art and animation
- the original macOS implementation and interaction design

## License

MIT. Please also see the original upstream repository for its history and attribution.
