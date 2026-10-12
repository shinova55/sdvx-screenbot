import json
import socket
import threading
import time
import pytest
from sdvxbot.api import SpiceClient, Controller, APIError, rc4


class Server:
    def __init__(self, mode="ok", password=""):
        self.mode, self.password = mode,password
        self.requests = []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1",0))
        self.sock.listen()
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self.serve,daemon=True)
        self.thread.start()

    def serve(self):
        connection,_ = self.sock.accept()
        cipher = rc4(self.password.encode()) if self.password else None
        def crypt(data):
            return bytes(b ^ next(cipher) for b in data) if cipher else data
        try:
            with connection:
                while True:
                    buf = bytearray()
                    while not buf or buf[-1] != 0:
                        chunk = connection.recv(1)
                        if not chunk:
                            return
                        buf.extend(crypt(chunk))
                    r = json.loads(buf[:-1])
                    self.requests.append(r)
                    if self.mode == "eof":
                        return
                    if self.mode == "timeout":
                        time.sleep(.2)
                        return
                    data = [["BT-A",0.0,False]] if r["function"] == "read" else []
                    response = dict(id=r["id"]+(self.mode == "id"), errors=["bad"] if self.mode == "error" else [], data=data)
                    payload = crypt(json.dumps(response).encode()+b"\0")
                    # Deliberately fragment both the JSON and terminating NUL.
                    for i in range(0,len(payload),3):
                        connection.sendall(payload[i:i+3])
        except (ConnectionError,OSError):
            pass
        finally:
            self.sock.close()


@pytest.mark.parametrize("password",["","test-password"])
def test_roundtrip_fragmentation_discovery_and_reset(password):
    server = Server(password=password)
    client = SpiceClient(port=server.port,password=password,timeout=1)
    control = Controller(client)
    assert control.discover()["buttons"][0][0] == "BT-A"
    control.write("buttons",{"BT-A":1})
    control.write("buttons",{"BT-A":1})
    control.write("analogs",{"VOL-L":.25})
    control.reset(terminal=True)
    control.write("buttons",{"BT-A":1})
    client.close()
    server.thread.join(1)
    assert len(server.requests) == 6
    assert server.requests[2]["params"] == [["BT-A",1.0]]
    assert server.requests[4]["params"] == [["BT-A"]]
    assert server.requests[5]["params"] == [["VOL-L"]]


@pytest.mark.parametrize("mode",["id","error","eof","timeout"])
def test_failure_invalidates_connection(mode):
    server = Server(mode)
    client = SpiceClient(port=server.port,timeout=.08)
    with pytest.raises(APIError):
        client.call("buttons","read")
    assert client.sock is None
    server.thread.join(1)


def test_dry_run_validation_and_rc4_vector():
    c = Controller()
    c.write("buttons",{"BT-A":1},1)
    assert c.events[0]["value"] == 1
    with pytest.raises(ValueError):
        c.write("analogs",{"x":float("nan")})
    cipher = rc4(b"Key")
    assert bytes(b ^ next(cipher) for b in b"Plaintext").hex() == "bbf316e8d940af0ad3"
    with pytest.raises(ValueError):
        SpiceClient(host="8.8.8.8")
