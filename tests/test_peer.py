"""Tests for the peer bridge: pure-Python logic only (no aiortc / aiohttp)."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vmux import config
from vmux.peer import PeerBridge, _IdTaken, _parse_ice, random_peer_id

# ── random_peer_id ────────────────────────────────────────────────────────── #

_ADJECTIVES = [
    "amber","azure","bronze","cobalt","coral","crimson","ember","fern",
    "gold","indigo","jade","lunar","maple","onyx","opal","pine","rose",
    "ruby","sage","slate","steel","teal","topaz","violet","zinc",
]
_NOUNS = [
    "brook","canyon","cedar","cliff","coast","delta","drift","dune","fjord",
    "forge","glade","grove","haven","horizon","isle","lagoon","mesa","mist",
    "peak","range","ridge","river","shore","summit","vale","wave",
]


def test_random_peer_id_format():
    pid = random_peer_id()
    parts = pid.split("-")
    assert len(parts) == 3, "expected adj-noun-<12hex>"
    adj, noun, hex_suffix = parts
    assert adj in _ADJECTIVES
    assert noun in _NOUNS
    # 12 hex chars (secrets.token_hex(6) = 48 bits of entropy)
    assert len(hex_suffix) == 12
    assert all(c in "0123456789abcdef" for c in hex_suffix)


def test_random_peer_id_is_random():
    ids = {random_peer_id() for _ in range(20)}
    assert len(ids) > 1, "20 calls should not all return the same ID"


# ── Config peer fields ────────────────────────────────────────────────────── #

def test_config_peer_defaults():
    c = config.Config()
    assert c.peer_id == ""
    assert c.peer_password == ""
    assert "peerjs" in c.peerjs_host or "azurewebsites" in c.peerjs_host
    assert c.peerjs_port == 443
    assert c.peerjs_path == "/"
    assert c.peerjs_key == "peerjs"


def test_config_peer_fields_not_in_editable_dict():
    # peer settings are server-side only; they must not be exposed to the UI
    d = config.Config().editable_dict()
    for key in ("peer_id", "peer_password", "peerjs_host", "peerjs_port", "peerjs_path", "peerjs_key"):
        assert key not in d


def test_load_peer_section_from_yaml(tmp_path):
    cfgfile = tmp_path / "config.yaml"
    cfgfile.write_text(
        "peer:\n"
        "  host: my.peerjs.example.com\n"
        "  port: 9000\n"
        "  path: /p\n"
        "  key: mykey\n"
    )
    c = config.load(str(cfgfile))
    assert c.peerjs_host == "my.peerjs.example.com"
    assert c.peerjs_port == 9000
    assert c.peerjs_path == "/p"
    assert c.peerjs_key == "mykey"


def test_load_peer_password_from_yaml(tmp_path):
    cfgfile = tmp_path / "config.yaml"
    cfgfile.write_text("peer:\n  password: s3cr3t\n")
    c = config.load(str(cfgfile))
    assert c.peer_password == "s3cr3t"


def test_load_missing_peer_section_uses_defaults(tmp_path):
    cfgfile = tmp_path / "config.yaml"
    cfgfile.write_text("poll_interval: 1.0\n")
    c = config.load(str(cfgfile))
    assert c.peerjs_port == 443
    assert c.peerjs_key == "peerjs"
    assert c.peer_password == ""


def test_id_taken_is_exception():
    exc = _IdTaken("amber-brook-a3f2c8b1d4e2")
    assert isinstance(exc, Exception)
    assert "amber-brook" in str(exc)


# ── Hub._peer_bridge integration ──────────────────────────────────────────── #

class _FakeWS:
    async def send_json(self, _):
        pass


class _MockBridge:
    def __init__(self):
        self.calls = []

    def notify(self, payload):
        self.calls.append(payload)


def _make_hub():
    from vmux.poller import Hub
    return Hub(config.Config())


def test_hub_peer_bridge_defaults_to_none():
    h = _make_hub()
    assert h._peer_bridge is None


def test_broadcast_calls_bridge_notify():
    h = _make_hub()
    bridge = _MockBridge()
    h._peer_bridge = bridge
    asyncio.run(h.broadcast())
    assert len(bridge.calls) == 1
    assert "panes" in bridge.calls[0]


def test_broadcast_without_bridge_does_not_crash():
    h = _make_hub()
    h._peer_bridge = None
    asyncio.run(h.broadcast())  # should not raise


def test_broadcast_swallows_bridge_exception():
    class _BadBridge:
        def notify(self, _):
            raise RuntimeError("boom")

    h = _make_hub()
    h._peer_bridge = _BadBridge()
    asyncio.run(h.broadcast())  # should not propagate


# ── PeerBridge.notify ─────────────────────────────────────────────────────── #

def _make_bridge():
    return PeerBridge(config.Config(), None, "test-peer-0000")


def test_notify_calls_all_listeners():
    b = _make_bridge()
    received = []
    b._hub_listeners.add(received.append)
    b.notify({"type": "state", "panes": []})
    assert received == [{"type": "state", "panes": []}]


def test_notify_with_no_listeners_does_not_crash():
    b = _make_bridge()
    b.notify({"type": "state", "panes": []})


def test_notify_evicts_dead_listener():
    b = _make_bridge()

    def bad(_):
        raise ValueError("dead")

    b._hub_listeners.add(bad)
    b.notify({"type": "state", "panes": []})
    assert bad not in b._hub_listeners


def test_notify_calls_remaining_after_dead_one():
    b = _make_bridge()
    good = []

    def bad(_):
        raise ValueError("dead")

    b._hub_listeners.add(bad)
    b._hub_listeners.add(good.append)
    b.notify({"panes": []})
    assert good == [{"panes": []}]


# ── _parse_ice ────────────────────────────────────────────────────────────── #

def test_parse_ice_returns_none_when_aiortc_missing(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "aiortc.sdp":
            raise ImportError("aiortc not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    result = _parse_ice({"candidate": "candidate:1 1 UDP 123 1.2.3.4 5000 typ host"})
    assert result is None


def test_parse_ice_returns_none_for_empty_candidate():
    assert _parse_ice({}) is None
    assert _parse_ice({"candidate": ""}) is None
