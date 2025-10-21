"""
Comprehensive unit tests for ChronoMap v2.1.0.

Includes:
- All original v2.0.0 tests (65+)
- All new v2.1.0 feature tests
- Fixes for correct error types and async methods

Run with: pytest tests/test_chronomap.py -v
"""

import pytest
import asyncio
import time
import json
import pickle
import tempfile
import threading
import random
from pathlib import Path
from datetime import datetime, timedelta
from chronomap import (
    ChronoMap,
    AsyncChronoMap,
    ChronoMapError,
    ChronoMapKeyError,
    ChronoMapTypeError,
    ChronoMapValueError,
)


# ============================================================================
# Basic Operations Tests
# ============================================================================

class TestBasicOperations:
    """Test core put, get, delete operations."""

    def test_put_and_get(self):
        cm = ChronoMap()
        cm.put('key', 'value')
        assert cm.get('key') == 'value'

    def test_put_with_timestamp(self):
        cm = ChronoMap()
        cm.put('key', 'value1', timestamp=100)
        cm.put('key', 'value2', timestamp=200)
        assert cm.get('key', timestamp=150) == 'value1'
        assert cm.get('key', timestamp=250) == 'value2'
    
    def test_put_with_datetime_string(self):
        cm = ChronoMap()
        cm.put('key', 'value1', timestamp="2025-01-01T00:00:00")
        cm.put('key', 'value2', timestamp="2025-01-02T00:00:00")
        
        dt1 = datetime(2025, 1, 1, 12, 0, 0)
        assert cm.get('key', timestamp=dt1) == 'value1'
    
    def test_put_with_datetime_object(self):
        cm = ChronoMap()
        dt1 = datetime(2025, 1, 1, 0, 0, 0)
        dt2 = datetime(2025, 1, 2, 0, 0, 0)
        
        cm.put('key', 'value1', timestamp=dt1)
        cm.put('key', 'value2', timestamp=dt2)
        
        assert cm.get('key', timestamp=dt1) == 'value1'
        assert cm.get('key', timestamp=dt2) == 'value2'

    def test_get_default(self):
        cm = ChronoMap()
        assert cm.get('nonexistent', default='default') == 'default'

    def test_get_strict_raises(self):
        cm = ChronoMap()
        with pytest.raises(ChronoMapKeyError):
            cm.get('nonexistent', strict=True)

    def test_delete(self):
        cm = ChronoMap()
        cm.put('key', 'value')
        assert cm.delete('key') is True
        assert cm.delete('key') is False
        assert 'key' not in cm

    def test_empty_map(self):
        cm = ChronoMap()
        assert len(cm) == 0
        assert not cm
        assert list(cm.keys()) == []


# ============================================================================
# TTL / Expiry Tests
# ============================================================================

class TestTTL:
    """Test TTL and key expiration."""

    def test_ttl_expiry(self):
        cm = ChronoMap()
        cm.put('temp', 'value', ttl=0.1)
        assert cm.get('temp') == 'value'
        time.sleep(0.15)
        assert cm.get('temp') is None

    def test_ttl_strict_raises(self):
        cm = ChronoMap()
        cm.put('temp', 'value', ttl=0.1)
        time.sleep(0.15)
        with pytest.raises(ChronoMapKeyError):
            cm.get('temp', strict=True)

    def test_ttl_contains(self):
        cm = ChronoMap()
        cm.put('temp', 'value', ttl=0.1)
        assert 'temp' in cm
        time.sleep(0.15)
        assert 'temp' not in cm

    def test_ttl_negative_raises(self):
        cm = ChronoMap()
        with pytest.raises(ChronoMapValueError):
            cm.put('key', 'value', ttl=-1)

    def test_clean_expired_keys(self):
        cm = ChronoMap()
        cm.put('temp1', 'v1', ttl=0.1)
        cm.put('temp2', 'v2', ttl=0.1)
        cm.put('perm', 'v3')
        time.sleep(0.15)
        removed = cm.clean_expired_keys()
        assert removed == 2
        assert 'perm' in cm


# ============================================================================
# Batch Operations Tests
# ============================================================================

class TestBatchOperations:
    """Test batch put and delete operations."""

    def test_put_many(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2, 'c': 3})
        assert cm['a'] == 1
        assert cm['b'] == 2
        assert cm['c'] == 3

    def test_put_many_with_ttl(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2}, ttl=0.1)
        assert cm['a'] == 1
        time.sleep(0.15)
        assert cm.get('a') is None

    def test_delete_many(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2, 'c': 3})
        deleted = cm.delete_many(['a', 'b', 'nonexistent'])
        assert deleted == 2
        assert 'a' not in cm
        assert 'b' not in cm
        assert 'c' in cm


# ============================================================================
# Advanced Query Tests
# ============================================================================

class TestAdvancedQueries:
    """Test range queries and latest keys."""

    def test_get_range(self):
        cm = ChronoMap()
        cm.put('temp', 20, timestamp=100)
        cm.put('temp', 22, timestamp=200)
        cm.put('temp', 24, timestamp=300)
        
        result = cm.get_range('temp', start_ts=150, end_ts=250)
        assert len(result) == 1
        assert result[0] == (200, 22)

    def test_get_range_all(self):
        cm = ChronoMap()
        cm.put('temp', 20, timestamp=100)
        cm.put('temp', 22, timestamp=200)
        
        result = cm.get_range('temp')
        assert len(result) == 2

    def test_get_latest_keys(self):
        cm = ChronoMap()
        cm.put('a', 1, timestamp=100)
        cm.put('b', 2, timestamp=200)
        cm.put('c', 3, timestamp=300)
        
        latest = cm.get_latest_keys(2)
        assert len(latest) == 2
        assert latest[0][0] == 'c'  # Most recent
        assert latest[1][0] == 'b'

    def test_get_keys_by_value(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 1, 'c': 2})
        keys = cm.get_keys_by_value(1)
        assert set(keys) == {'a', 'b'}


# ============================================================================
# Snapshot, Diff, Rollback Tests
# ============================================================================

class TestSnapshotDiffRollback:
    """Test snapshot, diff, and rollback functionality."""

    def test_snapshot(self):
        cm = ChronoMap()
        cm['key'] = 'value1'
        snap = cm.snapshot()
        cm['key'] = 'value2'
        assert cm['key'] == 'value2'
        assert snap['key'] == 'value1'

    def test_rollback(self):
        cm = ChronoMap()
        cm['key'] = 'value1'
        snap = cm.snapshot()
        cm['key'] = 'value2'
        cm['new_key'] = 'new_value'
        cm.rollback(snap)
        assert cm['key'] == 'value1'
        assert 'new_key' not in cm

    def test_rollback_invalid_type(self):
        cm = ChronoMap()
        with pytest.raises(ChronoMapTypeError):
            cm.rollback({'not': 'a chronomap'})

    def test_diff(self):
        cm1 = ChronoMap()
        cm2 = ChronoMap()
        cm1.put_many({'a': 1, 'b': 2})
        cm2.put_many({'a': 1, 'b': 3, 'c': 4})
        
        diff = cm1.diff(cm2)
        assert 'b' in diff  # Different value
        assert 'c' in diff  # Only in cm2

    def test_diff_detailed(self):
        cm1 = ChronoMap()
        cm2 = ChronoMap()
        cm1['a'] = 1
        cm2['a'] = 2
        
        changes = cm1.diff_detailed(cm2)
        assert len(changes) == 1
        assert changes[0] == ('a', 2, 1)


# ============================================================================
# Merge Tests
# ============================================================================

class TestMerge:
    """Test merge functionality."""

    def test_merge_timestamp_strategy(self):
        cm1 = ChronoMap()
        cm2 = ChronoMap()
        cm1.put('a', 1, timestamp=100)
        cm2.put('a', 2, timestamp=200)
        
        cm1.merge(cm2, strategy='timestamp')
        history = cm1.history('a')
        assert len(history) == 2
        assert history[0] == (100, 1)
        assert history[1] == (200, 2)

    def test_merge_overwrite_strategy(self):
        cm1 = ChronoMap()
        cm2 = ChronoMap()
        cm1.put('a', 1, timestamp=100)
        cm2.put('a', 2, timestamp=200)
        
        cm1.merge(cm2, strategy='overwrite')
        assert cm1['a'] == 2

    def test_merge_invalid_strategy(self):
        cm1 = ChronoMap()
        cm2 = ChronoMap()
        with pytest.raises(ChronoMapValueError):
            cm1.merge(cm2, strategy='invalid')

    def test_merge_invalid_type(self):
        cm = ChronoMap()
        with pytest.raises(ChronoMapTypeError):
            cm.merge({'not': 'a chronomap'})


# ============================================================================
# Magic Methods Tests
# ============================================================================

class TestMagicMethods:
    """Test Pythonic magic methods."""

    def test_getitem(self):
        cm = ChronoMap()
        cm.put('key', 'value')
        assert cm['key'] == 'value'

    def test_getitem_raises(self):
        cm = ChronoMap()
        with pytest.raises(ChronoMapKeyError):
            _ = cm['nonexistent']

    def test_setitem(self):
        cm = ChronoMap()
        cm['key'] = 'value'
        assert cm.get('key') == 'value'

    def test_delitem(self):
        cm = ChronoMap()
        cm['key'] = 'value'
        del cm['key']
        assert 'key' not in cm

    def test_delitem_raises(self):
        cm = ChronoMap()
        with pytest.raises(ChronoMapKeyError):
            del cm['nonexistent']

    def test_len(self):
        cm = ChronoMap()
        assert len(cm) == 0
        cm.put_many({'a': 1, 'b': 2, 'c': 3})
        assert len(cm) == 3

    def test_contains(self):
        cm = ChronoMap()
        cm['key'] = 'value'
        assert 'key' in cm
        assert 'nonexistent' not in cm

    def test_bool(self):
        cm = ChronoMap()
        assert not cm
        cm['key'] = 'value'
        assert cm

    def test_eq(self):
        cm1 = ChronoMap()
        cm2 = ChronoMap()
        cm1.put_many({'a': 1, 'b': 2})
        cm2.put_many({'a': 1, 'b': 2})
        assert cm1 == cm2
        
        cm2['b'] = 3
        assert cm1 != cm2

    def test_iter(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2, 'c': 3})
        keys = list(cm)
        assert set(keys) == {'a', 'b', 'c'}


# ============================================================================
# Iteration Tests
# ============================================================================

class TestIteration:
    """Test iteration methods."""

    def test_keys(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2})
        assert set(cm.keys()) == {'a', 'b'}

    def test_values(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2})
        assert set(cm.values()) == {1, 2}

    def test_items(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2})
        assert set(cm.items()) == {('a', 1), ('b', 2)}

    def test_iter_history(self):
        cm = ChronoMap()
        cm.put('key', 'v1', timestamp=100)
        cm.put('key', 'v2', timestamp=200)
        
        history = list(cm.iter_history('key'))
        assert len(history) == 2
        assert history[0] == (100, 'v1')
        assert history[1] == (200, 'v2')


# ============================================================================
# Utility Methods Tests
# ============================================================================

class TestUtilityMethods:
    """Test utility methods."""

    def test_latest(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2})
        assert cm.latest() == {'a': 1, 'b': 2}

    def test_history(self):
        cm = ChronoMap()
        cm.put('key', 'v1', timestamp=100)
        cm.put('key', 'v2', timestamp=200)
        
        history = cm.history('key')
        assert len(history) == 2
        assert history[0] == (100, 'v1')

    def test_clear(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2})
        cm.clear()
        assert len(cm) == 0
        assert cm.latest() == {}

    def test_repr(self):
        cm = ChronoMap()
        cm['key'] = 'value'
        repr_str = repr(cm)
        assert 'ChronoMap' in repr_str
        assert 'key' in repr_str


# ============================================================================
# Validation Tests
# ============================================================================

class TestValidation:
    """Test input validation."""

    def test_unhashable_key_raises(self):
        cm = ChronoMap()
        with pytest.raises(ChronoMapTypeError):
            cm.put(['unhashable', 'list'], 'value')

    def test_invalid_timestamp_type_raises(self):
        cm = ChronoMap()
        with pytest.raises(ChronoMapTypeError):
            cm.put('key', 'value', timestamp=1+2j)  # complex number

    def test_invalid_timestamp_value_raises(self):
        cm = ChronoMap()
        with pytest.raises(ChronoMapValueError):
            cm.put('key', 'value', timestamp=float('inf'))

    # Updated: Invalid datetime string raises ValueError, not TypeError
    def test_invalid_datetime_string_raises(self):
        cm = ChronoMap()
        with pytest.raises(ChronoMapValueError, match="Invalid datetime string"):
            cm.put('key', 'value', timestamp='not a number')


# ============================================================================
# Persistence Tests
# ============================================================================

class TestPersistence:
    """Test serialization and persistence."""

    def test_to_dict_from_dict(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2})
        
        data = cm.to_dict()
        cm2 = ChronoMap.from_dict(data)
        
        assert cm2['a'] == 1
        assert cm2['b'] == 2

    def test_save_load_json(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2})
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'test.json'
            cm.save_json(filepath)
            cm2 = ChronoMap.load_json(filepath)
            
            assert cm2['a'] == 1
            assert cm2['b'] == 2

    def test_save_load_pickle(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2, 'c': [1, 2, 3]})
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'test.pkl'
            cm.save_pickle(filepath)
            cm2 = ChronoMap.load_pickle(filepath)
            
            assert cm2['a'] == 1
            assert cm2['c'] == [1, 2, 3]


# ============================================================================
# Thread Safety Tests
# ============================================================================

class TestThreadSafety:
    """Test thread safety of operations."""

    def test_concurrent_puts(self):
        cm = ChronoMap()
        
        def put_values(start, count):
            for i in range(start, start + count):
                cm.put(f'key{i}', i)
        
        threads = []
        for i in range(5):
            t = threading.Thread(target=put_values, args=(i*100, 100))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(cm) == 500

    def test_concurrent_reads_writes(self):
        cm = ChronoMap()
        cm.put_many({f'key{i}': i for i in range(100)})
        
        results = []
        
        def reader():
            for _ in range(100):
                results.append(cm.get('key50'))
        
        def writer():
            for i in range(100):
                cm.put('key50', i)
        
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=reader))
            threads.append(threading.Thread(target=writer))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should complete without errors
        assert len(results) > 0

    def test_concurrent_snapshot_modify(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2})
        
        snapshots = []
        
        def take_snapshot():
            for _ in range(10):
                snapshots.append(cm.snapshot())
                time.sleep(0.001)
        
        def modify():
            for i in range(10):
                cm.put('a', i)
                time.sleep(0.001)
        
        t1 = threading.Thread(target=take_snapshot)
        t2 = threading.Thread(target=modify)
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        assert len(snapshots) == 10


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_put_same_timestamp_multiple_values(self):
        cm = ChronoMap()
        cm.put('key', 'v1', timestamp=100)
        cm.put('key', 'v2', timestamp=100)
        
        # Later put should be retrievable
        assert cm.get('key', timestamp=100) == 'v2'

    def test_get_before_first_timestamp(self):
        cm = ChronoMap()
        cm.put('key', 'value', timestamp=100)
        assert cm.get('key', timestamp=50) is None

    def test_empty_history(self):
        cm = ChronoMap()
        assert cm.history('nonexistent') == []

    def test_delete_nonexistent(self):
        cm = ChronoMap()
        assert cm.delete('nonexistent') is False

    def test_large_history(self):
        cm = ChronoMap()
        for i in range(1000):
            cm.put('key', i, timestamp=i)
        
        history = cm.history('key')
        assert len(history) == 1000
        assert cm.get('key', timestamp=500) == 500

    def test_none_as_value(self):
        cm = ChronoMap()
        cm['key'] = None
        assert cm['key'] is None
        assert 'key' in cm

    def test_complex_objects_as_values(self):
        cm = ChronoMap()
        cm['dict'] = {'nested': {'value': 123}}
        cm['list'] = [1, 2, [3, 4]]
        
        assert cm['dict']['nested']['value'] == 123
        assert cm['list'][2][1] == 4


# ============================================================================
# Debug Mode Tests
# ============================================================================

class TestDebugMode:
    """Test debug logging."""

    def test_debug_mode_enabled(self):
        cm = ChronoMap(debug=True)
        cm.put('key', 'value')
        # Should not raise, just enable logging
        assert cm.get('key') == 'value'


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests combining multiple features."""

    def test_full_workflow(self):
        """Test a complete workflow with multiple features."""
        cm = ChronoMap(debug=False)
        cm.put_many({'user1': 'active', 'user2': 'active', 'user3': 'inactive'})
        
        snap1 = cm.snapshot()
        cm['user1'] = 'inactive'
        cm['user4'] = 'active'
        
        active_users = cm.get_keys_by_value('active')
        assert set(active_users) == {'user2', 'user4'}
        
        changed = cm.diff(snap1)
        assert 'user1' in changed
        assert 'user4' in changed
        
        cm.rollback(snap1)
        assert cm['user1'] == 'active'
        assert 'user4' not in cm
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'state.pkl'
            cm.save_pickle(filepath)
            cm2 = ChronoMap.load_pickle(filepath)
            assert cm2 == cm

    def test_time_series_scenario(self):
        cm = ChronoMap()
        for hour in range(24):
            temp = 20 + (hour % 12)
            cm.put('temperature', temp, timestamp=hour * 3600)
        morning_temps = cm.get_range('temperature', start_ts=0, end_ts=12*3600)
        assert len(morning_temps) == 13
        full_history = cm.history('temperature')
        assert len(full_history) == 24

    def test_session_management_scenario(self):
        cm = ChronoMap()
        cm.put('session1', {'user': 'alice'}, ttl=0.2)
        cm.put('session2', {'user': 'bob'}, ttl=0.2)
        cm.put('session3', {'user': 'charlie'}, ttl=0.2)
        assert len(cm) == 3
        time.sleep(0.25)
        assert len(cm) == 0


# ============================================================================
# Event Hooks Tests (NEW in v2.1.0)
# ============================================================================

class TestEventHooks:
    """Test event callback functionality."""
    
    def test_on_change_callback(self):
        cm = ChronoMap()
        changes = []
        def track_change(key, old, new, ts):
            changes.append((key, old, new))
        cm.on_change(track_change)
        cm['key1'] = 'value1'
        cm['key1'] = 'value2'
        cm['key2'] = 'value3'
        assert len(changes) == 3
        assert changes[0] == ('key1', None, 'value1')
        assert changes[1] == ('key1', 'value1', 'value2')
        assert changes[2] == ('key2', None, 'value3')
    
    def test_multiple_callbacks(self):
        cm = ChronoMap()
        results1 = []
        results2 = []
        cm.on_change(lambda k, o, n, t: results1.append(k))
        cm.on_change(lambda k, o, n, t: results2.append(n))
        cm['key'] = 'value'
        assert 'key' in results1
        assert 'value' in results2
    
    def test_remove_callback(self):
        cm = ChronoMap()
        changes = []
        def callback(k, o, n, t):
            changes.append(k)
        cm.on_change(callback)
        cm['key1'] = 'val1'
        assert len(changes) == 1
        cm.remove_change_callback(callback)
        cm['key2'] = 'val2'
        assert len(changes) == 1

    def test_callback_exception_handling(self, caplog):
        cm = ChronoMap()
        def bad_callback(k, o, n, t):
            raise RuntimeError("Callback failed")
        cm.on_change(bad_callback)
        with caplog.at_level("ERROR"):
            cm['key'] = 'value'
        assert "Error in change callback" in caplog.text


# ============================================================================
# Query & Analytics Tests (NEW in v2.1.0)
# ============================================================================

class TestQueryAnalytics:
    """Test query and analytics features."""
    
    def test_query_filter(self):
        cm = ChronoMap()
        cm.put_many({'a': 10, 'b': 20, 'c': 30, 'd': 5})
        result = cm.query(lambda k, v: v > 15)
        assert result == {'b': 20, 'c': 30}
    
    def test_query_with_key_filter(self):
        cm = ChronoMap()
        cm.put_many({'user:1': 'active', 'user:2': 'inactive', 'admin:1': 'active'})
        result = cm.query(lambda k, v: k.startswith('user') and v == 'active')
        assert result == {'user:1': 'active'}
    
    def test_aggregate_sum(self):
        cm = ChronoMap()
        cm.put_many({'score1': 10, 'score2': 20, 'score3': 30})
        total = cm.aggregate(sum)
        assert total == 60
    
    def test_aggregate_average(self):
        cm = ChronoMap()
        cm.put_many({'val1': 10, 'val2': 20, 'val3': 30})
        avg = cm.aggregate(lambda vals: sum(vals) / len(vals))
        assert avg == 20
    
    def test_aggregate_specific_keys(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2, 'c': 3, 'd': 100})
        total = cm.aggregate(sum, keys=['a', 'b', 'c'])
        assert total == 6
    
    def test_count(self):
        cm = ChronoMap()
        cm.put_many({'a': 10, 'b': 20, 'c': 30})
        assert cm.count() == 3
        assert cm.count(lambda k, v: v > 15) == 2


# ============================================================================
# History Management Tests (Enhanced in v2.1.0)
# ============================================================================

class TestHistoryManagement:
    """Test history pruning and management."""
    
    def test_prune_history_keep_last(self):
        cm = ChronoMap()
        for i in range(100):
            cm.put('key', i, timestamp=i)
        removed = cm.prune_history('key', keep_last=10)
        assert removed == 90
        history = cm.history('key')
        assert len(history) == 10
        assert history[0][1] == 90
    
    def test_prune_history_older_than(self):
        cm = ChronoMap()
        cm.put('key', 'old', timestamp=100)
        cm.put('key', 'recent', timestamp=500)
        removed = cm.prune_history('key', older_than=300)
        assert removed == 1
        history = cm.history('key')
        assert len(history) == 1
        assert history[0][1] == 'recent'
    
    def test_prune_history_datetime_string(self):
        cm = ChronoMap()
        dt_old = datetime(2024, 1, 1)
        dt_new = datetime(2025, 1, 1)
        cm.put('key', 'old', timestamp=dt_old)
        cm.put('key', 'new', timestamp=dt_new)
        removed = cm.prune_history('key', older_than="2024-06-01T00:00:00")
        assert removed == 1
    
    def test_prune_all_history(self):
        cm = ChronoMap()
        for key in ['a', 'b', 'c']:
            for i in range(50):
                cm.put(key, i, timestamp=i)
        total_removed = cm.prune_all_history(keep_last=10)
        assert total_removed == 120


# ============================================================================
# Context Manager Tests (NEW in v2.1.0)
# ============================================================================

class TestContextManager:
    """Test snapshot context manager."""
    
    def test_snapshot_context_success(self):
        cm = ChronoMap()
        cm['key'] = 'original'
        with cm.snapshot_context():
            cm['key'] = 'modified'
        assert cm['key'] == 'modified'
    
    def test_snapshot_context_rollback_on_exception(self):
        cm = ChronoMap()
        cm['key'] = 'original'
        try:
            with cm.snapshot_context():
                cm['key'] = 'modified'
                cm['new_key'] = 'new_value'
                raise ValueError("Test exception")
        except ValueError:
            pass
        assert cm['key'] == 'original'
        assert 'new_key' not in cm


# ============================================================================
# Statistics Tests (NEW in v2.1.0)
# ============================================================================

class TestStatistics:
    """Test operation statistics tracking."""
    
    def test_stats_tracking(self):
        cm = ChronoMap()
        cm['a'] = 1
        cm['b'] = 2
        stats = cm.get_stats()
        assert stats['writes'] == 2
        _ = cm['a']
        _ = cm.get('b')
        stats = cm.get_stats()
        assert stats['reads'] == 2
        del cm['a']
        stats = cm.get_stats()
        assert stats['deletes'] == 1
        snap = cm.snapshot()
        stats = cm.get_stats()
        assert stats['snapshots'] == 1
    
    def test_reset_stats(self):
        cm = ChronoMap()
        cm['key'] = 'value'
        _ = cm['key']
        stats = cm.get_stats()
        assert stats['writes'] > 0
        assert stats['reads'] > 0
        cm.reset_stats()
        stats = cm.get_stats()
        assert stats['writes'] == 0
        assert stats['reads'] == 0


# ============================================================================
# Compression Tests (NEW in v2.1.0)
# ============================================================================

class TestCompression:
    """Test compression functionality."""
    
    def test_to_dict_compressed(self):
        cm = ChronoMap()
        cm.put_many({f'key{i}': f'value{i}' * 100 for i in range(100)})
        compressed = cm.to_dict(compress=True)
        assert isinstance(compressed, bytes)
        normal = cm.to_dict(compress=False)
        import pickle
        normal_size = len(pickle.dumps(normal))
        assert len(compressed) < normal_size
    
    def test_save_load_compressed_pickle(self):
        cm = ChronoMap()
        cm.put_many({'a': 1, 'b': 2, 'c': 3})
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'compressed.pkl'
            cm.save_pickle(filepath, compress=True)
            cm2 = ChronoMap.load_pickle(filepath)
            assert cm2['a'] == 1
            assert cm2['b'] == 2
    
    def test_load_pickle_auto_detect_compression(self):
        cm = ChronoMap()
        cm.put_many({'x': 42})
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = Path(tmpdir) / 'normal.pkl'
            p2 = Path(tmpdir) / 'compressed.pkl'
            cm.save_pickle(p1, compress=False)
            cm.save_pickle(p2, compress=True)
            cm1 = ChronoMap.load_pickle(p1)
            cm2 = ChronoMap.load_pickle(p2)
            assert cm1['x'] == 42
            assert cm2['x'] == 42


# ============================================================================
# Pandas Export Tests (NEW in v2.1.0)
# ============================================================================

class TestPandasExport:
    """Test Pandas DataFrame export."""
    
    def test_to_dataframe(self):
        pytest.importorskip("pandas")
        cm = ChronoMap()
        cm.put('temp', 20, timestamp=100)
        cm.put('temp', 22, timestamp=200)
        cm.put('temp', 24, timestamp=300)
        df = cm.to_dataframe()
        assert len(df) == 3
        assert set(df.columns) >= {'key', 'value', 'timestamp', 'datetime', 'version'}
        assert df['value'].tolist() == [20, 22, 24]
    
    def test_to_dataframe_without_pandas(self):
        cm = ChronoMap()
        cm.put('key', 'value')
        import sys
        original_pandas = sys.modules.get('pandas', None)
        sys.modules['pandas'] = None
        try:
            with pytest.raises(ImportError, match="pandas is required"):
                cm.to_dataframe()
        finally:
            if original_pandas is not None:
                sys.modules['pandas'] = original_pandas
            else:
                sys.modules.pop('pandas', None)


# ============================================================================
# Concurrency Tests (Enhanced with RWLock)
# ============================================================================

class TestConcurrency:
    """Test concurrency with read-write locks."""
    
    def test_rwlock_concurrent_reads(self):
        cm = ChronoMap(use_rwlock=True)
        cm.put_many({f'key{i}': i for i in range(100)})
        results = []
        def reader():
            for _ in range(50):
                val = cm.get('key50')
                results.append(val)
        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert all(v == 50 for v in results)
        assert len(results) == 500

    def test_rwlock_prevents_corruption(self):
        cm = ChronoMap(use_rwlock=True)
        barrier = threading.Barrier(3)
        def writer(id):
            for i in range(10):
                cm.put(f'key{id}', i)
            barrier.wait()
        t1 = threading.Thread(target=writer, args=(1,))
        t2 = threading.Thread(target=writer, args=(2,))
        t1.start()
        t2.start()
        barrier.wait()
        assert len(cm.history('key1')) == 10
        assert len(cm.history('key2')) == 10
        assert cm['key1'] == 9
        assert cm['key2'] == 9

    def test_rwlock_vs_rlock_performance_hint(self):
        cm1 = ChronoMap(use_rwlock=False)
        cm2 = ChronoMap(use_rwlock=True)
        cm1['a'] = 1
        cm2['a'] = 1
        assert cm1['a'] == cm2['a']


# ============================================================================
# AsyncChronoMap Tests (NEW in v2.1.0)
# ============================================================================

class TestAsyncChronoMap:
    """Test async version."""

    @pytest.mark.asyncio
    async def test_async_put_get(self):
        cm = AsyncChronoMap()
        await cm.put('key', 'value')
        assert await cm.get('key') == 'value'

    @pytest.mark.asyncio
    async def test_async_delete(self):
        cm = AsyncChronoMap()
        await cm.put('key', 'value')
        existed = await cm.delete('key')
        assert existed is True
        assert await cm.get('key', default=None) is None

    @pytest.mark.asyncio
    async def test_async_snapshot(self):
        cm = AsyncChronoMap()
        await cm.put('key', 'v1')
        snap = await cm.snapshot()
        await cm.put('key', 'v2')
        assert await cm.get('key') == 'v2'
        assert await snap.get('key') == 'v1'

    @pytest.mark.asyncio
    async def test_async_on_change_sync_callback(self):
        cm = AsyncChronoMap()
        log = []
        cm.on_change(lambda k, o, n, t: log.append((k, n)))
        await cm.put('k', 'v')
        assert log == [('k', 'v')]

    @pytest.mark.asyncio
    async def test_async_on_change_async_callback(self):
        cm = AsyncChronoMap()
        log = []
        async def async_cb(k, o, n, t):
            log.append((k, n))
        cm.on_change(async_cb)
        await cm.put('k', 'v')
        assert log == [('k', 'v')]

    @pytest.mark.asyncio
    async def test_async_keys_latest(self):
        cm = AsyncChronoMap()
        await cm.put_many({'a': 1, 'b': 2})
        keys = await cm.keys()
        latest = await cm.latest()
        assert set(keys) == {'a', 'b'}
        assert latest == {'a': 1, 'b': 2}


# ============================================================================
# Backward Compatibility & Edge Cases
# ============================================================================

class TestBackwardCompatibility:
    """Ensure v2.0.0 behavior still works."""

    def test_load_v2_0_0_json(self):
        data = {
            'store': {'key': [(100.0, 'value')]},
            'ttl': {},
            'snapshot_time': None
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'old.json'
            with open(path, 'w') as f:
                json.dump(data, f)
            cm = ChronoMap.load_json(path)
            assert cm['key'] == 'value'

    def test_repr_truncation(self):
        cm = ChronoMap()
        for i in range(20):
            cm[f'key{i}'] = i
        r = repr(cm)
        assert '...' in r
        assert len(r) < 200


# ============================================================================
# Run if executed directly
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])