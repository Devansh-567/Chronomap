import pytest
import time
from chronomap import ChronoMap

def test_basic_put_get():
    cm = ChronoMap()
    cm.put("key1", "value1")
    assert cm.get("key1") == "value1"

def test_get_nonexistent_key():
    cm = ChronoMap()
    assert cm.get("nonexistent") is None

def test_multiple_versions():
    cm = ChronoMap()
    cm.put("key", "v1", timestamp=100.0)
    cm.put("key", "v2", timestamp=200.0)
    cm.put("key", "v3", timestamp=300.0)
    assert cm.get("key", timestamp=150.0) == "v1"
    assert cm.get("key", timestamp=250.0) == "v2"
    assert cm.get("key", timestamp=350.0) == "v3"

def test_snapshot_diff():
    cm = ChronoMap()
    cm.put("key1", "value1")
    snap = cm.snapshot()
    cm.put("key1", "value2")
    assert cm.diff(snap) == {"key1"}
