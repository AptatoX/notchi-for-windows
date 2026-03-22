# Notchi for Windows

This folder contains a Windows port of Notchi. It keeps the core idea of the macOS app while adapting the UI and integration points for Windows:

- install Claude Code hooks
- receive live Claude events
- show active sessions in a small always-on-top desktop overlay
- use the original Notchi sprite sheets from the macOS app

## What works

- Windows hook installer for `~/.claude/settings.json`
- Live event listener over `127.0.0.1:8765`
- Multi-session activity view
- Multi-sprite island mode with one sprite per Claude Code session
- Click a sprite to select that session and expand its details
- Prompt, tool, duration, recent event display, and Claude reply previews
- Original sprite-sheet animation from the upstream project assets
- Emotion-aware sprite switching for `neutral`, `happy`, `sad`, and `sob`

## What is not ported yet

- macOS notch UI
- Sparkle auto-updates
- Keychain integration
- sound effects
- exact parity with the original macOS layout and panel styling

## Run

```powershell
cd windows
python app.py
```

Then click `Install Hook` in the app and start using Claude Code.

## Notes

- The port is intentionally standalone and does not touch the original Xcode project.
- The hook uses PowerShell and TCP instead of a Unix socket, which is a better fit for Windows.
- Click the island area to show or hide the detailed session panel.
- When multiple Claude Code sessions are active, each session gets its own sprite on the island.

## Attribution

- Based on the original [sk-ruban/notchi](https://github.com/sk-ruban/notchi) project.
- Original sprite assets and the app concept remain credited to the upstream project and its authors.
