"""PeerJS signaling + WebRTC DataChannel bridge.

When a peer ID is configured, vmux registers as a peer on the PeerJS
signaling server.  Remote vmux PWA clients can then connect by entering the
peer ID — no VPN or port forwarding required.

Protocol over the single DataChannel (all messages are JSON strings):

  client → server  {"t":"req","id":N,"method":"GET","path":"/api/state","body":null}
  server → client  {"t":"res","id":N,"status":200,"body":{...}}
  server → client  {"t":"ws","type":"state","panes":[...]}    (periodic push)

Install deps:  pip install "vmux[peer]"
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import uuid
from typing import Callable, Dict, Optional, Set, Tuple

log = logging.getLogger(__name__)

# Defaults — override via config.yaml peer: section
DEFAULT_PEERJS_HOST = "peerjs-hcbtcmc2dyecbxa6.centralus-01.azurewebsites.net"
DEFAULT_PEERJS_PORT = 443
DEFAULT_PEERJS_PATH = "/"
DEFAULT_PEERJS_KEY  = "peerjs"

_ADJECTIVES = [
    "amber", "azure", "bronze", "cobalt", "coral", "crimson", "ember", "fern",
    "gold", "indigo", "jade", "lunar", "maple", "onyx", "opal", "pine", "rose",
    "ruby", "sage", "slate", "steel", "teal", "topaz", "violet", "zinc",
]
_NOUNS = [
    "brook", "canyon", "cedar", "cliff", "coast", "delta", "drift", "dune",
    "fjord", "forge", "glade", "grove", "haven", "horizon", "isle", "lagoon",
    "mesa", "mist", "peak", "range", "ridge", "river", "shore", "summit",
    "vale", "wave",
]


def random_peer_id() -> str:
    """Return a memorable random ID like 'amber-brook-4729'."""
    return "{}-{}-{}".format(
        secrets.choice(_ADJECTIVES),
        secrets.choice(_NOUNS),
        secrets.randbelow(9000) + 1000,
    )


class PeerBridge:
    """Registers vmux as a WebRTC peer; proxies API calls through DataChannels.

    One instance is created at startup.  Each browser that calls
    ``peer.connect(peer_id)`` gets its own RTCPeerConnection and DataChannel.
    """

    def __init__(self, cfg, hub, peer_id: str) -> None:
        self.cfg     = cfg
        self.hub     = hub
        self.peer_id = peer_id
        self._stop   = False
        # sync callbacks: hub calls these after every broadcast
        self._hub_listeners: Set[Callable[[dict], None]] = set()

    # ------------------------------------------------------------------ #
    # Hub integration                                                      #
    # ------------------------------------------------------------------ #

    def notify(self, payload: dict) -> None:
        """Called by Hub.broadcast() after every poll tick."""
        dead: Set[Callable] = set()
        for cb in list(self._hub_listeners):
            try:
                cb(payload)
            except Exception:
                dead.add(cb)
        self._hub_listeners -= dead

    # ------------------------------------------------------------------ #
    # Public lifecycle                                                     #
    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        backoff = 2.0
        while not self._stop:
            try:
                await self._run_once()
                backoff = 2.0
            except Exception as exc:
                if self._stop:
                    break
                log.warning("[peer] disconnected (%s) — retrying in %.0fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 30.0)

    def stop(self) -> None:
        self._stop = True

    # ------------------------------------------------------------------ #
    # Signaling loop (one WebSocket lifetime)                             #
    # ------------------------------------------------------------------ #

    async def _run_once(self) -> None:
        try:
            import aiohttp
            from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "pip install 'vmux[peer]'  (needs aiortc + aiohttp)"
            ) from exc

        cfg  = self.cfg
        host = getattr(cfg, "peerjs_host", DEFAULT_PEERJS_HOST)
        port = getattr(cfg, "peerjs_port", DEFAULT_PEERJS_PORT)
        path = getattr(cfg, "peerjs_path", DEFAULT_PEERJS_PATH).rstrip("/")
        key  = getattr(cfg, "peerjs_key",  DEFAULT_PEERJS_KEY)

        scheme = "wss" if int(port) == 443 else "ws"
        token  = uuid.uuid4().hex
        ws_url = (
            f"{scheme}://{host}:{port}{path}/peerjs"
            f"?key={key}&id={self.peer_id}&token={token}"
        )
        log.info("[peer] connecting → %s  (id: %s)", ws_url.split("?")[0], self.peer_id)

        # (src_peer_id, connection_id) → RTCPeerConnection
        peers: Dict[Tuple[str, str], RTCPeerConnection] = {}

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url, heartbeat=25) as ws:
                # first message must be OPEN
                raw = await ws.receive(timeout=10)
                first = json.loads(raw.data)
                if first.get("type") != "OPEN":
                    raise RuntimeError("PeerJS server did not send OPEN: %s" % first)
                log.info("[peer] registered — share this ID with your vmux PWA: %s", self.peer_id)

                async def send(obj: dict) -> None:
                    await ws.send_json(obj)

                async for raw in ws:
                    if self._stop:
                        break
                    if raw.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
                    if raw.type != aiohttp.WSMsgType.TEXT:
                        continue

                    msg   = json.loads(raw.data)
                    mtype = msg.get("type", "")

                    if mtype == "HEARTBEAT":
                        await send({"type": "HEARTBEAT"})

                    elif mtype == "OFFER":
                        asyncio.create_task(self._handle_offer(msg, send, peers))

                    elif mtype == "CANDIDATE":
                        src     = msg.get("src", "")
                        payload = msg.get("payload", {})
                        conn_id = payload.get("connectionId", "")
                        pc      = peers.get((src, conn_id))
                        if pc and payload.get("candidate"):
                            ice = _parse_ice(payload["candidate"])
                            if ice:
                                try:
                                    await pc.addIceCandidate(ice)
                                except Exception as e:
                                    log.debug("[peer] ICE candidate error: %s", e)

    # ------------------------------------------------------------------ #
    # WebRTC offer handling                                               #
    # ------------------------------------------------------------------ #

    async def _handle_offer(
        self,
        msg: dict,
        send: Callable,
        peers: dict,
    ) -> None:
        try:
            from aiortc import RTCPeerConnection, RTCSessionDescription
        except ImportError:
            return

        src     = msg.get("src", "")
        payload = msg.get("payload", {})
        conn_id = payload.get("connectionId", uuid.uuid4().hex[:8])
        sdp_obj = payload.get("sdp", {})
        if not sdp_obj:
            return

        pc = RTCPeerConnection()
        peers[(src, conn_id)] = pc

        @pc.on("icecandidate")
        async def on_ice(candidate) -> None:
            if candidate is None:
                return
            await send({
                "type": "CANDIDATE",
                "dst":  src,
                "payload": {
                    "candidate": {
                        "candidate":     "candidate:" + candidate.candidate,
                        "sdpMid":        candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex,
                    },
                    "connectionId": conn_id,
                    "type": "data",
                },
            })

        @pc.on("datachannel")
        def on_dc(channel) -> None:
            asyncio.ensure_future(self._serve_channel(channel, src))

        @pc.on("connectionstatechange")
        async def on_state_change() -> None:
            if pc.connectionState in ("closed", "failed", "disconnected"):
                peers.pop((src, conn_id), None)

        sdp_str  = sdp_obj.get("sdp", sdp_obj) if isinstance(sdp_obj, dict) else sdp_obj
        sdp_type = sdp_obj.get("type", "offer") if isinstance(sdp_obj, dict) else "offer"

        await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp_str, type=sdp_type))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        await send({
            "type": "ANSWER",
            "dst":  src,
            "payload": {
                "sdp":           {"type": answer.type, "sdp": answer.sdp},
                "type":          "data",
                "connectionId":  conn_id,
                "serialization": "raw",
                "reliable":      True,
            },
        })

    # ------------------------------------------------------------------ #
    # DataChannel request/response + state push                          #
    # ------------------------------------------------------------------ #

    async def _serve_channel(self, channel, peer_label: str) -> None:
        """Serve one open DataChannel: proxy REST requests and push state."""
        cfg       = self.cfg
        local_url = "http://127.0.0.1:%d" % cfg.port
        token     = cfg.token or ""
        loop      = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        # send current snapshot immediately on connect
        queue.put_nowait(self.hub.snapshot())

        def on_hub_push(payload: dict) -> None:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, payload)
            except Exception:
                pass

        self._hub_listeners.add(on_hub_push)
        log.debug("[peer] channel open  ← %s", peer_label)

        try:
            import aiohttp
        except ImportError:
            self._hub_listeners.discard(on_hub_push)
            return

        async with aiohttp.ClientSession() as http:

            async def pusher() -> None:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    try:
                        channel.send(json.dumps({"t": "ws", **item}))
                    except Exception:
                        break

            push_task = asyncio.create_task(pusher())

            @channel.on("message")
            def on_message(data: str) -> None:
                asyncio.ensure_future(_proxy_request(data, channel, http, local_url, token))

            @channel.on("close")
            def on_close() -> None:
                queue.put_nowait(None)

            try:
                await push_task
            finally:
                self._hub_listeners.discard(on_hub_push)
                log.debug("[peer] channel closed ← %s", peer_label)


async def _proxy_request(
    data: str,
    channel,
    http,
    local_url: str,
    token: str,
) -> None:
    """Forward one DataChannel REST request to the local FastAPI server."""
    try:
        req = json.loads(data)
    except Exception:
        return
    if req.get("t") != "req":
        return

    rid    = req.get("id")
    method = req.get("method", "GET").upper()
    path   = req.get("path", "/api/state")
    body   = req.get("body")

    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token

    try:
        import aiohttp
        async with http.request(
            method,
            local_url + path,
            headers=headers,
            json=body,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp_body = await resp.json(content_type=None)
            status    = resp.status
    except Exception as exc:
        resp_body = {"detail": str(exc)}
        status    = 500

    try:
        channel.send(json.dumps({"t": "res", "id": rid, "status": status, "body": resp_body}))
    except Exception:
        pass


def _parse_ice(cand: dict) -> Optional[object]:
    """Parse a PeerJS ICE candidate dict into an aiortc RTCIceCandidate."""
    try:
        from aiortc.sdp import candidate_from_sdp
    except ImportError:
        return None

    raw = cand.get("candidate", "")
    if not raw:
        return None
    # strip leading "candidate:" prefix if present
    if raw.startswith("candidate:"):
        raw = raw[len("candidate:"):]
    try:
        ice = candidate_from_sdp(raw)
        ice.sdpMid        = cand.get("sdpMid")
        ice.sdpMLineIndex = cand.get("sdpMLineIndex")
        return ice
    except Exception:
        return None
