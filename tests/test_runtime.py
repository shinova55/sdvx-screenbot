"""Lifecycle checks use fake capture/listener; no desktop or game interaction."""
import sys
import types
import time
from pathlib import Path
import pytest
from sdvxbot.api import Controller
from sdvxbot.config import load
from sdvxbot.runtime import run
from sdvxbot.demo import frame_at

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("failure",["capture","panic","watchdog"])
def test_cleanup_on_capture_failure_and_panic(monkeypatch,tmp_path,failure):
    cfg = load(ROOT/"config.example.json")
    control = Controller()
    control.write("buttons",{"BT-A":1})
    listeners = []
    class Listener:
        def __init__(self,on_press):
            self.callback = on_press
            self.alive = False
            listeners.append(self)
        def start(self): self.alive = True
        def wait(self): pass
        def is_alive(self): return self.alive
        def stop(self): self.alive = False
    class Capture:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def grab(self,roi):
            if failure == "capture":
                raise OSError("Synthetic capture failure")
            if failure == "panic":
                listeners[0].callback("F12")
            else:
                time.sleep(.25)
            return frame_at(0,cfg)
    monkeypatch.setitem(sys.modules,"mss",types.SimpleNamespace(mss=Capture))
    keyboard = types.SimpleNamespace(Key=types.SimpleNamespace(f12="F12"),Listener=Listener)
    monkeypatch.setitem(sys.modules,"pynput",types.SimpleNamespace(keyboard=keyboard))
    if failure == "capture":
        with pytest.raises(OSError,match="Synthetic"):
            run(cfg,control,1,tmp_path/"events.json",preview=False)
    else:
        run(cfg,control,1,tmp_path/"events.json",preview=False)
    assert control.stopped
    assert not control.owned["buttons"]
    assert not listeners[0].alive
    assert (tmp_path/"events.json").exists()
