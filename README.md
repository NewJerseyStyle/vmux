# vmux

**Drive your Claude Code / Codex / Gemini CLI swarm from your phone.**

When an agent stops to ask *"Do you want me to make this edit to `auth.py`?"*, `vmux` parses the dialog out of the tmux pane, ships the menu options to your phone, and lets you tap **Yes** from the couch — or the train, or a meeting room.

It's the missing control panel for the [setup I wrote about here](https://imitation-alpha.github.io/blog/orchestrating-coding-agents.html) — running 10+ CLI coding agents in parallel without it collapsing into chaos.

![vmux PWA — list of agent sessions, color-coded by status](docs/images/panel-list-view.jpg)
![vmux PWA — open session detail with menu options and action keys](docs/images/panel-session-view.jpg)

---

## ⭐ Star to vote — 100 stars unlocks the public release

This repo is currently a placeholder. The prototype is real, runs on my machine every day, and is what powers my own ten-agent workflow — but it isn't yet packaged for other people.

Polishing it into something installable, secure-by-default, documented, and supportable is roughly 5× the work of the prototype itself. Before I commit to that, I'd like a real signal that it's worth doing.

**If this repo crosses 100 stars, I'll port the prototype into a polished open-source release.**

If you'd use this — star the repo. GitHub will notify you the moment v0.1 ships. No mailing list, no DMs, no follow-up needed from you.

---

## What the prototype does today

A small FastAPI server reads and writes tmux panes; a single-file React PWA renders the swarm in your browser.

### Grid view — every agent at a glance

One card per CLI agent, color-coded by what it's doing:

- 🟢 **Idle** — at a shell prompt
- 🟡 **Working** — output is scrolling
- 🔴 **Needs input** — a dialog is waiting (pulsing border, tappable menu buttons right on the card)
- 🟠 **Error** — recent traceback or error pattern detected
- ⚫ **Offline** — tmux pane gone

### Dialog parsing, not screen-scraping

For Claude Code specifically, `vmux` parses the TUI box characters (`╭ ╰ │ ❯`) out of the pane and surfaces the menu choices as native buttons. You tap **Accept** / **Reject** / **Edit** without ever touching arrow keys.

Agents that aren't Claude Code (a long-running build, a Codex shell, a Gemini CLI) fall back to regex detection on configurable patterns: `(y/n)`, `Do you want to…`, `Press enter to…`, etc.

### Detail view — drive the session

Tap a card and you get:

- the full pane output, with diff highlighting
- menu-option buttons when a Claude dialog is active
- a text input with voice dictation (where the platform supports it)
- an action row: `Ctrl+C`, `Esc`, arrows, `Tab`, `Enter`

No SSH attach, no `<C-b> s` dance, no scrollback hunt.

### Broadcast

Select a subset of agents on the home screen and send the same prompt to all of them. Useful for *"run the test suite"*, *"summarize what you changed"*, *"stand by, I'm switching machines"*.

### Notifications

When any agent transitions to **needs input**, a beep plays and the page title flips to `(!) vmux`. With permission granted, a system notification fires while the tab is backgrounded — so you can put the phone down and trust it'll find you.

### Stays on your network

- Default bind is `127.0.0.1` — meant to be reached via SSH tunnel or [Tailscale](https://tailscale.com).
- LAN mode requires a bearer token. Empty token + `0.0.0.0` is a fail-fast error, not a footgun.
- No cloud, no account, no telemetry. Your sessions stay on your hardware.

---

## What's missing for a v1

These are the items I'd tackle if the star threshold hits — roughly in priority order:

1. **One-command install.** Today it's `pip install -r requirements.txt`, hand-edit `config.yaml`, find pane targets via `tmux list-panes`. v1 should be a single binary or `pipx install vmux` plus auto-discovery of running agents.
2. **Cross-agent piping.** Let one agent read another's last N lines without copy-paste.
3. **Linux + WSL parity.** Today's prototype assumes a macOS/Linux home box; the path defaults and clipboard integration need work elsewhere.
4. **iOS PWA polish.** The PWA installs and runs, but Safari quirks (no Web Speech API, scroll-restoration weirdness, push limits) deserve a proper pass.
5. **Pluggable agent kinds.** Today there are two: `claude-code` (TUI box parsing) and `generic` (regex). Adding Codex and Gemini CLI as first-class kinds with their own dialog parsers.
6. **Auth that's nicer than a bearer token.** Probably WebAuthn / passkeys, scoped to a Tailscale tailnet.
7. **A real test story across platforms** — the current 35 tests run against a live tmux, which is right, but only on macOS.

---

## How it works (short version)

- **Backend:** FastAPI + WebSocket. Polls each configured tmux pane every ~500 ms via `tmux capture-pane`, runs detectors, broadcasts state diffs to connected clients. Sends keystrokes back via `tmux send-keys -l` (literal mode — shell-safe).
- **Frontend:** Single HTML file with React via CDN. No build step, no bundler. Service worker caches the shell so it's installable as a PWA.
- **Config:** YAML — list your tmux panes, name them, mark them `claude-code` or `generic`. That's it.

The whole thing is intentionally small. It's plumbing between tmux and a phone, not a platform.

---

## FAQ

**Why not [tmate / Warp / Zellij / iSH / browser terminal X]?**
Those put you back in a terminal. The point of `vmux` is *not* being in a terminal — it's a status surface tuned for *"I have ten agents running and want to know which one needs me right now."* Different problem, different UI.

**Will it work with Codex / Gemini CLI / aider / [agent X]?**
The prototype already handles them via `kind: generic` (regex on `(y/n)`, "Do you want to…", etc.). For v1, each one would get a dedicated dialog parser like Claude Code has today, so menu choices become tappable buttons instead of "type y and press enter."

**Why a 100-star threshold instead of just shipping?**
Honest answer: porting a personal-use tool into something installable, secure-by-default, documented, and supportable is roughly 5× the prototype work. I want a real signal that the time is justified.

**What if it doesn't hit 100?**
It stays a personal tool. The [accompanying blog post](https://imitation-alpha.github.io/blog/orchestrating-coding-agents.html) covers the rest of the setup, which is the 80% you can replicate today with off-the-shelf tools (tmux, Tailscale, Terminus, Oh-My-Tmux).

**Is this just a SSH client?**
No — an SSH client puts you in a shell. `vmux` reads tmux pane state, *interprets* it (idle / working / needs-input / error / offline), and gives you a tappable surface specifically for orchestrating multiple agents. The SSH client is the fallback when `vmux` can't help.

**Will it work without Tailscale?**
Yes. Tailscale is the easiest path because it gives you a stable hostname reachable from your phone without exposing anything publicly. Plain SSH tunneling works too. So does LAN mode with a bearer token, if you trust your WiFi.

---

## License

MIT when the code lands.

## Author

[@imitation-alpha](https://github.com/imitation-alpha) · [X](https://x.com/imitation_alpha)
