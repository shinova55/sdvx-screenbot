"""Spice TCP protocol. See SOURCES.md for verified upstream signatures."""
import ipaddress
import json
import math
import socket
import threading
import time


class APIError(RuntimeError):
    pass


def rc4(key):
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) % 256
        s[i], s[j] = s[j], s[i]
    i = j = 0
    while True:
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        yield s[(s[i] + s[j]) % 256]


class SpiceClient:
    def __init__(self, host="127.0.0.1", port=1337, password="", timeout=0.3):
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError("Only numeric loopback addresses are allowed")
        self.sock = socket.create_connection((host, port), timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.timeout = timeout
        self.cipher = rc4(password.encode()) if password else None
        self.lock = threading.RLock()
        self.seq = 0

    def crypt(self, data):
        return bytes(b ^ next(self.cipher) for b in data) if self.cipher else data

    def call(self, module, function, params=None):
        with self.lock:
            if self.sock is None:
                raise APIError("Connection closed; no automatic replay of writes")
            self.seq += 1
            request = dict(id=self.seq, module=module, function=function, params=params or [])
            try:
                deadline = time.monotonic() + self.timeout
                self.sock.settimeout(self.timeout)
                self.sock.sendall(self.crypt(json.dumps(request, allow_nan=False).encode() + b"\0"))
                buf = bytearray()
                while not buf or buf[-1] != 0:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("API response deadline exceeded")
                    self.sock.settimeout(remaining)
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        raise APIError("API disconnected")
                    buf.extend(self.crypt(chunk))
                    if len(buf) > 1024 * 1024:
                        raise APIError("Oversized response")
                response = json.loads(buf[:-1])
                if not isinstance(response, dict):
                    raise APIError("Response must be an object")
                if response.get("id") != self.seq:
                    raise APIError("Response ID mismatch")
                if not isinstance(response.get("errors"), list) or not isinstance(response.get("data"), list):
                    raise APIError("Malformed response schema")
                if response["errors"]:
                    raise APIError(str(response["errors"]))
                return response["data"]
            except (OSError, ValueError, APIError) as exc:
                self.close()
                raise APIError(str(exc)) from exc

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None


class Controller:
    def __init__(self, client=None):
        self.client = client
        self.owned = {"buttons": set(), "analogs": set()}
        self.states = {}
        self.events = []
        self.stopped = False
        self.lock = threading.RLock()

    def discover(self):
        if not self.client:
            return {}
        data = {m: self.client.call(m, "read") for m in self.owned}
        for module, rows in data.items():
            for row in rows:
                if (not isinstance(row, list) or len(row) < 3 or not isinstance(row[0], str)
                        or not isinstance(row[1], (float,int)) or not math.isfinite(row[1])
                        or not isinstance(row[2], bool)):
                    raise APIError(f"Malformed {module} discovery row")
        return data

    def validate(self, button_names, analog_names=()):
        data = self.discover()
        for module, names in (("buttons", button_names), ("analogs", analog_names)):
            available = {row[0] for row in data.get(module, [])}
            missing = set(names) - available
            if self.client and missing:
                raise APIError(f"Missing {module}: {sorted(missing)}")
            active = {row[0] for row in data.get(module, []) if row[2]}
            if active.intersection(names):
                raise APIError("Selected controls already overridden; reset them explicitly first")
        return data

    def write(self, module, values, now=None):
        with self.lock:
            if self.stopped:
                return
            if module not in self.owned:
                raise ValueError(module)
            changed = []
            for name, value in values.items():
                if not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError("Input must be finite and within [0,1]")
                if self.states.get((module, name)) != value:
                    changed.append([name, float(value)])
            if not changed:
                return
            # Own before send: a partial server application still needs cleanup.
            self.owned[module].update(name for name, _ in changed)
            if self.client:
                self.client.call(module, "write", changed)
            for name, value in changed:
                self.states[module, name] = value
                self.events.append(dict(time=now, module=module, name=name, value=value))

    def reset(self, terminal=False):
        with self.lock:
            self.stopped |= terminal
            failures = []
            for module, names in self.owned.items():
                if names and self.client:
                    try:
                        self.client.call(module, "write_reset", [[n] for n in sorted(names)])
                    except APIError as exc:
                        failures.append(str(exc))
                names.clear()
            self.states.clear()
            if failures:
                raise APIError("Reset unconfirmed; stop/restart Spice to clear overrides: " + "; ".join(failures))

    def release(self, module, name):
        with self.lock:
            if name in self.owned[module]:
                if self.client:
                    self.client.call(module, "write_reset", [[name]])
                self.owned[module].discard(name)
                self.states.pop((module,name),None)
