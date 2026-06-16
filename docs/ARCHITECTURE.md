# Architecture

vmux is small. It's a pipeline: **route → cheapen → deliver.** Triage which pane
needs you, make the decision a single tap, put it on whatever screen you're at.

## Data flow

```
tmux ──capture-pane──▶ poller ──detect()──▶ PaneState ──WebSocket──▶ local web UI
  ▲                       (every ~poll_interval)              │
  └────────────── tmux send-keys ◀── REST /api/{…} ◀─────────┘
                                                              │
                                              PeerBridge (peer.py, optional)
                                                              │  PeerJS WS signaling
                                                              ▼
                                                      PeerJS cloud server
                                                              │  WebRTC DataChannel
                                                              ▼
                                                    remote browser PWA
                                              (vmux.imitationalpha.com/?peer=ID)
```

1. **`poller.py` — `Hub.poll_once()`** runs on a loop (`poll_interval`, default
   0.7s; an action `kick()`s an immediate re-poll). It lists panes, captures each
   concurrently (`asyncio.to_thread`), diffs against the last capture, and builds
   a `PaneState` per pane. `Hub.broadcast()` pushes the snapshot to all connected
   WebSocket clients and, if a `PeerBridge` is attached, calls `bridge.notify()`.
2. **`detectors.py`** turns raw pane text into a status + a parsed menu. Pure
   functions — input is text, output is a `DetectResult`. Two strategies:
   Claude Code TUI box parsing (`parse_claude_menu`, the `╭ │ ❯` characters) and
   a generic regex path for everything else. User-supplied regexes run via the
   `regex` module with a hard timeout so a bad pattern can't wedge the loop.
3. **`models.py` — `PaneState`** is the JSON contract. `to_dict()` is exactly
   what the frontend receives. Keep it stable.
4. **`server.py`** is the FastAPI app: REST for actions, a WebSocket that pushes
   the full snapshot every tick, static serving of `vmux/web/`. All API routes
   are behind a bearer-token dependency (`require_auth`); the WebSocket checks
   the token before `accept()`. On startup, if `cfg.peer_id` is set, a
   `PeerBridge` task is started and wired to the Hub.
5. **`peer.py`** — optional WebRTC peer bridge (`vmux[peer]` extra, requires
   `aiortc` and `aiohttp`). `PeerBridge` opens a WebSocket to a PeerJS signaling
   server, registers the peer ID, and handles incoming WebRTC offers. For each
   remote browser that connects, it creates an `RTCPeerConnection`, opens a
   DataChannel, and multiplexes the full API over it:
   - `{t:"req", method, path, body}` → local aiohttp REST call → `{t:"res", …}`
   - `{t:"ws", data}` — pushed unsolicited when `notify()` is called by `Hub.broadcast()`
   The DataChannel protocol intentionally mirrors the direct HTTP/WebSocket API so
   the browser-side `api()` and `useSwarm()` functions need only a thin shim.
6. **`web/index.html`** is the whole frontend — React + htm (vendored in
   `web/vendor/`, no build step). One codebase, two idioms: a macOS sidebar
   split-view and an iOS bottom-sheet, chosen at runtime by media query. When
   `?peer=ID` is present in the URL (or stored in `localStorage`), the PWA uses
   `peerjs.min.js` (vendored) to connect via DataChannel instead of a direct
   WebSocket. The `PeerGate` component handles the connection / error states.
7. **`web/` on GitHub Pages** — the `vmux/web/` directory is published to
   `vmux.imitationalpha.com` via a GitHub Actions workflow. All asset paths are
   relative (`./vendor/...`) so the app works at both a domain root and a sub-path.
   The service worker (`sw.js`) caches the shell; cache key is versioned to force
   refresh on updates.

## State contract (`PaneState`)

`id` (tmux pane id) · `target` (session:window.pane) · `name` · `kind`
(`claude-code` / `generic` / `shell`) · `status` · `title` · `question` ·
`menu` (parsed options) · `preview` / `lines` · `updated` · `changed`.

## Config & settings

`config.py` loads optional YAML (everything has a default, so vmux runs with no
config). The Settings UI edits a live-mutable subset (`editable_dict` /
`apply_patch`) which is persisted to a JSON **overlay** file layered over the
YAML — so the user's hand-authored `config.yaml` (comments, token) is never
rewritten. `apply_patch` validates everything (regex compile + caps, enum checks)
and recompiles patterns so changes apply on the next poll.

## Safety invariants (don't break these)

- tmux is driven via argument lists, never a shell; named keys are allow-listed;
  pane ids are format-checked; literal text uses `send-keys -l --`.
- Auth uses `hmac.compare_digest`. The token never appears in API responses.
- User regexes always run with a timeout.
- In `web/index.html`, `style` props are objects, not strings.
