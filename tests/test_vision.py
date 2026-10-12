import copy
from pathlib import Path
import cv2
import numpy as np
from sdvxbot.config import load
from sdvxbot.api import Controller
from sdvxbot.vision import Detector, Detection, propose_judgment, rectify
from sdvxbot.tracking import Tracker,Engine
from sdvxbot.demo import run,NOTES

ROOT = Path(__file__).resolve().parents[1]


def config():
    return load(ROOT/"config.example.json")


def test_demo_all_presses_and_holds(tmp_path):
    events = run(config(),tmp_path)
    presses = [e for e in events if e["value"] == 1]
    assert len(presses) == len(NOTES)
    for lane,hit,duration in NOTES:
        name = config()["buttons"][lane]
        candidates = [e for e in presses if e["name"] == name and abs(e["time"]-hit) < .025]
        assert len(candidates) == 1
        press = candidates[0]
        release = next(e for e in events if e["name"] == name and e["value"] == 0 and e["time"] > press["time"])
        if duration:
            assert abs(release["time"]-(hit+duration)) < .035
        else:
            assert .015 <= release["time"]-press["time"] <= .04


def test_tracking_identity_and_occlusion():
    tracker = Tracker()
    first = tracker.update([Detection(0,10,17,False),Detection(0,80,87,False)],0,600)
    ids = [t.id for t in first]
    tracker.update([Detection(0,14,21,False),Detection(0,84,91,False)],.016,600)
    after = tracker.update([Detection(0,88,95,False),Detection(0,18,25,False)],.032,600)
    assert [t.id for t in after] == ids
    assert all(200 < t.velocity < 300 for t in after)
    assert len(tracker.update([],.05,600)) == 2
    assert tracker.update([],.2,600) == []


def test_static_false_positive_and_frame_gap():
    c = config()
    control = Controller()
    engine = Engine(c,control)
    for i in range(50):
        engine.step([Detection(0,510,520,False)],[None,None],i/120)
    assert not any(e["value"] == 1 for e in control.events)
    control.write("buttons",{"BT-A":1})
    engine.step([], [None,None],2)
    assert control.states["buttons","BT-A"] == 0


def test_masks_judgment_and_rectification():
    c = config()
    image = np.zeros((600,400,3),np.uint8)
    cv2.line(image,(0,520),(399,520),(255,255,255),2)
    assert abs(propose_judgment(image)-520) < 4
    assert np.array_equal(rectify(image,c["geometry"]),image)
    image[:] = 0
    cv2.rectangle(image,(120,514),(128,520),(255,255,0),-1)
    result = Detector(c["vision"]).lasers(image,520)
    assert .30 < result[0] < .33
    assert result[1] is None


def test_laser_abstains_on_jump_and_loss():
    c = config()
    c["laser"]["enabled"] = True
    control = Controller()
    engine = Engine(c,control)
    engine.step([], [.2,None],0)
    engine.step([], [.21,None],.01)
    assert abs(control.states["analogs","VOL-L"]-.5025) < 1e-8
    engine.step([], [.9,None],.02)
    assert ("analogs","VOL-L") not in control.states
    engine.step([], [None,None],.03)
    assert not control.owned["analogs"]


def test_processing_age_is_extrapolated():
    c = config()
    control = Controller()
    engine = Engine(c,control)
    engine.step([Detection(0,481,488,False)],[None,None],0)
    engine.step([Detection(0,493,500,False)],[None,None],.05)
    engine.step([Detection(0,505,512,False)],[None,None],.135,capture_time=.10)
    assert control.states["buttons","BT-A"] == 1
