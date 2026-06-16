# vmux — quickstart (MVP)

Run a phone/desktop control panel over your tmux agent swarm. No config needed to start.

> **Python 3.10+ required.** Python 3.9 reached end-of-life in October 2025.

## Run it

```bash
# from the repo root, with uv (recommended)
uv run python -m vmux

# or with plain pip
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
python -m vmux
```

Then open **http://127.0.0.1:8787**. That's it — vmux auto-discovers every tmux
pane, classifies each as `claude-code` / `generic` / `shell`, and shows the agents.
(Plain idle shells are hidden by default; add `--include-shells` to see them.)

## Reach it from anywhere — WebRTC (no VPN)

The easiest way to reach vmux remotely is the built-in peer bridge:

```bash
pip install "vmux[peer]"    # adds aiortc + aiohttp
vmux --peer                 # prompts for optional password, then prints the peer URL
```

On startup you'll see:

```
vmux peer password (press Enter to skip): ••••••••
vmux peer  -> https://vmux.imitationalpha.com/?peer=amber-brook-a3f2c8b1d4e2
```

Open that URL on any device, anywhere. The hosted page connects back to your machine
over a direct WebRTC channel — **no VPN, no port forwarding required**. The peer ID
is always auto-generated (high entropy) and resets on each restart. If you set a
password at startup, the remote browser will be prompted for it before gaining access.

**Linux dependencies for aiortc:**

```bash
sudo apt install libavdevice-dev libavfilter-dev libopus-dev libvpx-dev pkg-config
```

**macOS:** `brew install ffmpeg opus libvpx pkg-config`

## Reach it from your local network (Tailscale / SSH)

vmux binds `127.0.0.1` on purpose. Classic alternatives if you prefer LAN access:

- **Tailscale (easiest):** `vmux --host 0.0.0.0 --token "$(openssl rand -hex 16)"`
  then visit `http://<machine-tailscale-name>:8787/?token=<that-token>` on your phone.
- **SSH tunnel:** `ssh -L 8787:localhost:8787 you@box` and open `http://localhost:8787` on the phone.

`--host 0.0.0.0` with an empty token is a hard error, by design.

Install it as an app: in the phone browser, "Add to Home Screen". It runs full-screen
and notifies you (tap the bell icon once to grant permission) when an agent needs you.

## Using it

- **Grid** is triage-ordered: the agents that need you float to the top, color-coded
  (red = needs input, orange = error, yellow = working, green = idle, grey = offline).
- A red card shows the parsed question and **tappable menu buttons** — tap `1`/Yes
  without touching a keyboard.
- **Tap a card** for the full pane: scrollback, the menu, a text box (with `↵`), and an
  action row (`Ctrl+C`, `Esc`, `Tab`, arrows, `Enter`).
- **Broadcast:** toggle it, pick a few agents, send one message to all.

## Config (optional)

```bash
cp config.example.yaml config.yaml
uv run python -m vmux -c config.yaml
```

See `config.example.yaml` for poll interval, pinned panes, token, and detector patterns.

## Tests

```bash
uv run --extra dev pytest -q
```
