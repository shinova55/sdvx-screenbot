from pathlib import Path
import pytest
from sdvxbot.charts import parse_ksh,parse_vox,fit_sync

ROOT = Path(__file__).resolve().parents[1]/"fixtures"


def test_ksh_tempo_holds_and_fx_convention():
    chart = parse_ksh(ROOT/"example.ksh")
    assert next(e for e in chart["events"] if e["lane"] == "BT-B") == dict(lane="BT-B",time=.5,duration=1)
    assert next(e for e in chart["events"] if e["lane"] == "FX-L")["duration"] == 0
    assert next(e for e in chart["events"] if e["lane"] == "FX-R") == dict(lane="FX-R",time=1.5,duration=.75)


def test_unsupported_timing_rejected(tmp_path):
    f = tmp_path/"stop.ksh"
    f.write_text("t=120\n--\nstop=48\n1000|00|--\n--\n")
    with pytest.raises(ValueError,match="stop"):
        parse_ksh(f)


def test_vox_raw_only():
    data = parse_vox(ROOT/"structural.vox")
    assert data["sections"]["TRACK3"][0]["raw_position"] == [1,1,0]
    assert "UNVERIFIED" in data["warnings"][0]


def test_sync_clock_fit():
    result = fit_sync(ROOT/"sync.csv")
    assert result["clock_scale"] == pytest.approx(1.0002)
    assert result["offset_seconds"] == pytest.approx(1.25)
    assert result["residual_max_ms"] < 1e-8
