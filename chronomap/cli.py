import argparse
import json
import time
from pathlib import Path
from .chronomap import ChronoMap

"""
ChronoMap CLI - Command-line interface for experimenting with ChronoMap.

Usage:
    python -m chronomap                    # Interactive mode
    python -m chronomap --demo             # Run demo
    python -m chronomap --file data.json   # Load from file
"""

def interactive_mode():
    """Run interactive ChronoMap shell."""
    print("=" * 60)
    print("ChronoMap Interactive Shell (v2.1.0)")
    print("=" * 60)
    print("\nCommands:")
    print("  put <key> <value>        - Store a value")
    print("  get <key>                - Retrieve a value")
    print("  delete <key>             - Delete a key")
    print("  history <key>            - Show key history")
    print("  latest                   - Show all latest values")
    print("  query <expr>             - Filter keys (e.g., 'lambda k, v: v > 10')")
    print("  prune <key> <n>          - Keep last N versions")
    print("  stats                    - Show operation statistics")
    print("  snapshot                 - Take a snapshot")
    print("  rollback                 - Rollback to last snapshot")
    print("  clear                    - Clear all data")
    print("  save <file>              - Save to JSON file")
    print("  load <file>              - Load from JSON file")
    print("  help                     - Show this help")
    print("  exit                     - Exit shell")
    print()
    
    cm = ChronoMap(debug=False)
    snapshot_stack = []
    
    while True:
        try:
            cmd = input("chronomap> ").strip()
            if not cmd:
                continue
            
            parts = cmd.split(maxsplit=2)
            command = parts[0].lower()
            
            if command == 'exit':
                print("Goodbye!")
                break
            
            elif command == 'help':
                print("\nCommands:")
                print("  put <key> <value>        - Store a value")
                print("  get <key>                - Retrieve a value")
                print("  delete <key>             - Delete a key")
                print("  history <key>            - Show key history")
                print("  latest                   - Show all latest values")
                print("  query <expr>             - Filter keys (e.g., 'lambda k, v: v > 10')")
                print("  prune <key> <n>          - Keep last N versions")
                print("  stats                    - Show operation statistics")
                print("  snapshot                 - Take a snapshot")
                print("  rollback                 - Rollback to last snapshot")
                print("  clear                    - Clear all data")
                print("  save <file>              - Save to JSON file")
                print("  load <file>              - Load from JSON file")
                print("  exit                     - Exit shell\n")
            
            elif command == 'put':
                if len(parts) < 3:
                    print("Usage: put <key> <value>")
                    continue
                key = parts[1]
                value = parts[2]
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
                cm[key] = value
                print(f"✓ Stored: {key} = {value}")
            
            elif command == 'get':
                if len(parts) < 2:
                    print("Usage: get <key>")
                    continue
                key = parts[1]
                value = cm.get(key)
                if value is None:
                    print(f"✗ Key '{key}' not found")
                else:
                    print(f"→ {key} = {value}")
            
            elif command == 'delete':
                if len(parts) < 2:
                    print("Usage: delete <key>")
                    continue
                key = parts[1]
                if cm.delete(key):
                    print(f"✓ Deleted: {key}")
                else:
                    print(f"✗ Key '{key}' not found")
            
            elif command == 'history':
                if len(parts) < 2:
                    print("Usage: history <key>")
                    continue
                key = parts[1]
                history = cm.history(key)
                if not history:
                    print(f"✗ No history for key '{key}'")
                else:
                    print(f"\nHistory for '{key}':")
                    for ts, val in history:
                        dt = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts))
                        print(f"  {dt} ({ts:.2f}): {val}")
            
            elif command == 'latest':
                latest = cm.latest()
                if not latest:
                    print("✗ Map is empty")
                else:
                    print("\nLatest values:")
                    for key, value in sorted(latest.items()):
                        print(f"  {key}: {value}")
            
            elif command == 'query':
                if len(parts) < 2:
                    print("Usage: query <lambda expression>")
                    print("Example: query \"lambda k, v: isinstance(v, int) and v > 10\"")
                    continue
                expr = parts[1]
                try:
                    pred = eval(expr, {"__builtins__": {}}, {})
                    result = cm.query(pred)
                    if result:
                        print("\nQuery result:")
                        for k, v in result.items():
                            print(f"  {k}: {v}")
                    else:
                        print("No matching keys")
                except Exception as e:
                    print(f"✗ Query error: {e}")
            
            elif command == 'prune':
                if len(parts) < 3:
                    print("Usage: prune <key> <n>")
                    continue
                key = parts[1]
                try:
                    n = int(parts[2])
                    removed = cm.prune_history(key, keep_last=n)
                    print(f"✓ Pruned {removed} old versions, kept {n}")
                except Exception as e:
                    print(f"✗ Prune error: {e}")
            
            elif command == 'stats':
                stats = cm.get_stats()
                print("\nOperation Statistics:")
                for k, v in stats.items():
                    print(f"  {k}: {v}")
            
            elif command == 'snapshot':
                snap = cm.snapshot()
                snapshot_stack.append(snap)
                print(f"✓ Snapshot taken (total: {len(snapshot_stack)})")
            
            elif command == 'rollback':
                if not snapshot_stack:
                    print("✗ No snapshots available")
                else:
                    snap = snapshot_stack.pop()
                    cm.rollback(snap)
                    print(f"✓ Rolled back (remaining: {len(snapshot_stack)})")
            
            elif command == 'clear':
                cm.clear()
                print("✓ Cleared all data")
            
            elif command == 'save':
                if len(parts) < 2:
                    print("Usage: save <file>")
                    continue
                filepath = parts[1]
                cm.save_json(filepath)
                print(f"✓ Saved to {filepath}")
            
            elif command == 'load':
                if len(parts) < 2:
                    print("Usage: load <file>")
                    continue
                filepath = parts[1]
                cm = ChronoMap.load_json(filepath)
                snapshot_stack.clear()
                print(f"✓ Loaded from {filepath}")
            
            else:
                print(f"✗ Unknown command: {command}")
                print("Type 'help' for available commands")
        
        except KeyboardInterrupt:
            print("\nUse 'exit' to quit")
        except Exception as e:
            print(f"✗ Error: {e}")


def run_demo():
    """Run a demonstration of ChronoMap v2.1.0 features."""
    print("=" * 60)
    print("ChronoMap v2.1.0 Feature Demonstration")
    print("=" * 60)
    
    cm = ChronoMap(use_rwlock=True)
    
    # Basic operations
    print("\n1. Basic Operations")
    print("-" * 40)
    cm['name'] = 'Alice'
    cm['age'] = 30
    print(f"Stored: {cm.latest()}")
    
    # Event hooks
    print("\n2. Event Hooks")
    print("-" * 40)
    def log_change(k, o, n, t):
        print(f"  → {k}: {o} → {n}")
    cm.on_change(log_change)
    cm['age'] = 31
    cm['city'] = 'Paris'
    
    # Query & aggregation (isolated numeric demo)
    print("\n3. Query & Aggregation")
    print("-" * 40)
    cm_scores = ChronoMap()
    cm_scores.put_many({'score1': 85, 'score2': 92, 'score3': 78})
    high_scores = cm_scores.query(lambda k, v: isinstance(v, (int, float)) and v > 80)
    avg = cm_scores.aggregate(lambda vals: sum(vals) / len(vals), keys=['score1', 'score2', 'score3'])
    print(f"High scores: {high_scores}")
    print(f"Average score: {avg:.1f}")
    
    # History pruning
    print("\n4. History Pruning")
    print("-" * 40)
    for i in range(10):
        cm.put('sensor', i, timestamp=1000 + i)
    print(f"Before prune: {len(cm.history('sensor'))} versions")
    cm.prune_history('sensor', keep_last=3)
    print(f"After prune: {len(cm.history('sensor'))} versions (kept last 3)")
    
    # Snapshot context
    print("\n5. Snapshot Context Manager")
    print("-" * 40)
    cm['status'] = 'stable'
    try:
        with cm.snapshot_context():
            cm['status'] = 'testing'
            cm['temp'] = 'data'
            raise RuntimeError("Simulated failure")
    except RuntimeError:
        pass
    
    # Safely print after rollback
    status_val = cm.get('status')
    temp_val = cm.get('temp')
    print(f"After rollback: status={status_val}, temp={temp_val if temp_val is not None else 'N/A'}")
    
    # Stats
    print("\n6. Operation Statistics")
    print("-" * 40)
    stats = cm.get_stats()
    print(f"Writes: {stats['writes']}, Reads: {stats['reads']}")
    
    # Async note
    print("\n7. Async Support")
    print("-" * 40)
    print("Use AsyncChronoMap for asyncio applications:")
    print("  async with lock, await cm.put(...), etc.")
    
    # Persistence
    print("\n8. Persistence (with compression)")
    print("-" * 40)
    print("Save/load with compression via save_pickle(compress=True)")
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


def load_and_display(filepath: str):
    """Load and display ChronoMap from file."""
    path = Path(filepath)
    
    if not path.exists():
        print(f"Error: File '{filepath}' not found")
        return
    
    try:
        if path.suffix == '.json':
            cm = ChronoMap.load_json(filepath)
        elif path.suffix == '.pkl':
            cm = ChronoMap.load_pickle(filepath)
        else:
            print(f"Error: Unsupported file type '{path.suffix}'")
            return
        
        print(f"Loaded ChronoMap from {filepath}")
        print(f"Keys: {len(cm)}")
        print(f"Version: {getattr(cm, '_version', 'unknown')}")
        print(f"\nLatest values:")
        for key, value in sorted(cm.latest().items()):
            print(f"  {key}: {value}")
    
    except Exception as e:
        print(f"Error loading file: {e}")


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="ChronoMap v2.1.0 - Enhanced time-versioned key-value store",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m chronomap              Start interactive shell
  python -m chronomap --demo       Run feature demonstration
  python -m chronomap --file data.json   Load and display file
        """
    )
    
    parser.add_argument('--demo', action='store_true', help='Run feature demonstration')
    parser.add_argument('--file', '-f', type=str, help='Load and display ChronoMap from file')
    parser.add_argument('--version', '-v', action='store_true', help='Show version')
    
    args = parser.parse_args()
    
    if args.version:
        from chronomap import __version__
        print(f"ChronoMap version {__version__}")
        return
    
    if args.demo:
        run_demo()
    elif args.file:
        load_and_display(args.file)
    else:
        interactive_mode()


if __name__ == '__main__':
    main()
