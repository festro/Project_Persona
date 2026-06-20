"""Phase 3 control-plane EventBus -- one interface, two transports.

Per docs/ipc_decision.md: the Phase 3 daemon owns a one-way (components -> daemon),
fire-and-forget notification bus with a small fixed event vocabulary. Call sites depend
ONLY on the EventBus interface, never on a transport, so NATS (default, mesh-ready) and
the stdlib LoopbackBus (compat fallback) are a configuration choice, not a code fork.

This module ships the interface + the stdlib LoopbackBus (asyncio.start_server on
127.0.0.1, length-prefixed JSON frames, shared-token gated, single-host only). NatsBus
lives alongside it once nats-py is wired (it implements the same three coroutines).

Contract (the invariants the API relies on):
  - ONE-WAY: publishers send and forget; the server never replies. A publish must NEVER
    raise into or block the caller -- a missed event silently drops, a request never stalls.
  - FRESH ON START: the daemon binds the endpoint each start; there is no durable backlog
    (durability is JetStream's job, deferred to the Task Board / Phase 9).
  - SMALL VOCABULARY: `ping` today; profile_switched, ingest_complete, tts_speaking,
    task_ready planned (see EVENTS).
"""
import asyncio
import json
import os
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

# The fixed event vocabulary (docs/ipc_decision.md section 2). Not enforced -- a tiny,
# documented set that subscribers and publishers agree on; "*" subscribes to all.
EVENTS = ("ping", "profile_switched", "ingest_complete", "tts_speaking", "task_ready")

# 4-byte big-endian length prefix; cap a frame so a bad/hostile sender can't allocate huge.
_MAX_FRAME = 1 << 20  # 1 MiB

Handler = Callable[[str, Dict[str, Any]], Union[None, Awaitable[None]]]


def default_loopback_port() -> int:
    return int(os.getenv("IPC_LOOPBACK_PORT", "8791"))


class EventBus:
    """Transport-agnostic interface. Implementations: LoopbackBus, NatsBus."""

    async def start(self) -> None:
        """Bind/connect the subscriber endpoint (daemon side). Idempotent."""
        raise NotImplementedError

    async def stop(self) -> None:
        """Tear the endpoint down cleanly."""
        raise NotImplementedError

    async def publish(self, event: str, payload: Optional[Dict[str, Any]] = None) -> bool:
        """Fire-and-forget. Returns True if handed to the transport, False on any error.
        MUST NOT raise or block the caller for longer than a short timeout."""
        raise NotImplementedError

    async def subscribe(self, event: str, handler: Handler) -> None:
        """Register a handler for `event` (or "*" for all). Handler may be sync or async."""
        raise NotImplementedError


class LoopbackBus(EventBus):
    """Stdlib single-host fallback: asyncio.start_server + length-prefixed JSON, token-gated.

    The same object is both server (daemon: start() binds + subscribe() dispatches) and
    client (API: publish() opens a short-lived connection to the configured port). No mesh
    path -- loopback only.
    """

    def __init__(self, host: str = "127.0.0.1", port: Optional[int] = None,
                 token: str = "", connect_timeout: float = 1.0):
        self.host = host
        self.port = int(port if port is not None else default_loopback_port())
        self.token = token or ""
        self.connect_timeout = connect_timeout
        self._server: Optional[asyncio.AbstractServer] = None
        self._handlers: Dict[str, List[Handler]] = {}

    # -- daemon (subscriber) side ------------------------------------------------
    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(self._handle_conn, self.host, self.port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            try:
                await self._server.wait_closed()
            except Exception:  # noqa: BLE001
                pass
            self._server = None

    async def subscribe(self, event: str, handler: Handler) -> None:
        self._handlers.setdefault(event, []).append(handler)

    async def _handle_conn(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            hdr = await reader.readexactly(4)
            n = int.from_bytes(hdr, "big")
            if n <= 0 or n > _MAX_FRAME:
                return
            data = await reader.readexactly(n)
            msg = json.loads(data.decode("utf-8"))
            if not isinstance(msg, dict) or msg.get("token", "") != self.token:
                return  # reject: malformed or bad token
            event = str(msg.get("event") or "")
            payload = msg.get("payload") or {}
            if not isinstance(payload, dict):
                payload = {}
            await self._dispatch(event, payload)
        except (asyncio.IncompleteReadError, json.JSONDecodeError, UnicodeDecodeError):
            return
        except Exception:  # noqa: BLE001 -- a bad sender must never crash the listener
            return
        finally:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    async def _dispatch(self, event: str, payload: Dict[str, Any]) -> None:
        handlers = list(self._handlers.get(event, [])) + list(self._handlers.get("*", []))
        for h in handlers:
            try:
                res = h(event, payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:  # noqa: BLE001 -- one bad handler must not sink the rest
                continue

    # -- publisher (API) side ----------------------------------------------------
    async def publish(self, event: str, payload: Optional[Dict[str, Any]] = None) -> bool:
        frame_obj = {"event": event, "payload": payload or {}, "token": self.token}
        try:
            blob = json.dumps(frame_obj, ensure_ascii=False).encode("utf-8")
            if len(blob) > _MAX_FRAME:
                return False
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=self.connect_timeout)
            try:
                writer.write(len(blob).to_bytes(4, "big") + blob)
                await asyncio.wait_for(writer.drain(), timeout=self.connect_timeout)
            finally:
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), timeout=self.connect_timeout)
                except Exception:  # noqa: BLE001
                    pass
            return True
        except Exception:  # noqa: BLE001 -- one-way + never block the caller
            return False
