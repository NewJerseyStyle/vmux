# Changelog

All notable changes to vmux are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **WebRTC peer bridge** (`vmux[peer]` optional extra — `pip install "vmux[peer]"`).
  Start with `vmux --peer-id` to get a friendly peer ID (e.g. `amber-brook-4729`).
  A `PeerBridge` in `peer.py` connects to a PeerJS signaling server, accepts WebRTC
  offers from remote browsers, and multiplexes the full REST API + state push over a
  single DataChannel — no VPN, no port forwarding, $0 infrastructure.
- **Hosted PWA bridge** at `vmux.imitationalpha.com` (GitHub Pages, `vmux/web/`).
  Opening `https://vmux.imitationalpha.com/?peer=<id>` connects a remote browser
  directly to a local vmux server via P2P WebRTC. Works as a fallback when the local
  PWA install is not available.
- **`--peer-id` CLI flag** — pass an explicit ID or omit the value to auto-generate
  one. Startup prints the full remote-access URL.
- **PeerGate UI** — when a peer ID is detected in the URL or localStorage, the PWA
  shows a connection screen (status: connecting / open / error) instead of attempting
  a direct WebSocket. A "Use direct mode" link appears once the peer ID is set.
- **Peer ID shown in Settings** — the active peer ID and a disconnect / forget button
  appear in the "Remote access (WebRTC)" section of the Settings panel.
- **Friendly peer ID generator** (`peer.random_peer_id()`) — `<adjective>-<noun>-<4digits>`,
  e.g. `amber-brook-4729`, drawn from wordlists via `secrets.choice`.

### Changed

- **Python minimum raised to 3.10** — Python 3.9 reached EOL in October 2025.
  CI matrix now covers 3.10–3.13.

### Fixed

- All PWA asset paths made relative (`./vendor/...` instead of `/vendor/...`) so the
  app works both at a domain root and at a GitHub Pages sub-path (e.g. `/vmux/`).
- Service-worker cache version bumped to `vmux-v14`; manifest `start_url`/`scope`
  set to `"."` for portability.

## [0.1.0] — 2026-06-08

First public release.

### Added

- **Attention-router core.** FastAPI + WebSocket backend that polls tmux panes,
  detects status (idle / working / needs-input / error / offline), parses Claude
  Code TUI selection boxes into tappable menus, and drives panes via
  `tmux send-keys`. Generic agents detected via configurable regex.
- **Native PWA UI** (single-file React + htm, vendored, no build step):
  platform-adaptive — macOS sidebar split-view on desktop, iOS bottom-sheet on
  mobile — with Apple "Liquid Glass" styling and automatic light/dark.
- **Triage** grid/sidebar ordered by who needs you, with tappable menu buttons,
  a detail view with action keys + text input, and **broadcast** to many agents.
- **Settings** page: browser prefs (theme, glass, ambient motion, sound,
  notifications, default filter) plus live server config (poll interval,
  discovery, per-pane rename/kind, detector patterns, pane-name source),
  persisted to an overlay so a hand-authored `config.yaml` is never rewritten.
- **Connected-sessions** monitor with per-device disconnect.
- **Token gate** UI for unauthorized clients (paste token instead of a silent
  empty grid).
- **Notifications** (sound + system notification) when an agent needs input.
- Auto-discovery of tmux panes (no config required); optional `config.yaml`.

### Security

- Constant-time token comparison (`hmac.compare_digest`) on REST + WebSocket.
- Vendored React/htm same-origin (no third-party CDN / supply-chain exposure).
- ReDoS-bounded detection: user regexes run with a hard per-match timeout, plus
  a nested-quantifier linter and input caps.
- Fail-fast when binding a non-loopback address with an empty token.

### Packaging

- Installable via `pipx`/`pip`; the web UI ships inside the wheel.
- MIT licensed; CI (pytest + ruff + wheel-contents check) and a PyPI release
  workflow.

[Unreleased]: https://github.com/imitation-alpha/vmux/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/imitation-alpha/vmux/releases/tag/v0.1.0
