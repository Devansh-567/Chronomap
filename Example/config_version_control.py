"""
Configuration Version Control with ChronoMap
=============================================

This example demonstrates how to use ChronoMap as a configuration management
system with version control, audit trails, and instant rollback capabilities.

Perfect for:
- Managing application settings across environments
- Tracking who changed what configuration and when
- Rolling back to previous configurations when deployments fail
- A/B testing different configuration sets

Run this script: python config_version_control.py
"""

from chronomap import ChronoMap
from datetime import datetime
import json


def main():
    print("=" * 70)
    print("Configuration Version Control System with ChronoMap")
    print("=" * 70)
    print()

    # Initialize ChronoMap with history tracking and auto-cleanup
    # max_history=50 keeps last 50 config changes per setting
    # enable_ttl_cleanup=True automatically removes temporary test configs
    config = ChronoMap(
        max_history=50,
        cache_size=100,
        enable_ttl_cleanup=True
    )

    # Track all configuration changes for audit log
    audit_log = []

    def log_config_change(key, old_value, new_value, timestamp):
        """Callback function to create audit trail of all changes"""
        audit_log.append({
            'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
            'setting': key,
            'old_value': old_value,
            'new_value': new_value,
            'changed_by': 'admin'  # In real app, get from session
        })
        print(f"📝 Config changed: {key} = {new_value}")

    # Register the audit log callback
    config.on_change(log_config_change)

    # ========================================================================
    # SCENARIO 1: Initial Configuration Setup
    # ========================================================================
    print("\n📋 Step 1: Setting up initial production configuration")
    print("-" * 70)

    # Database settings
    config['database.host'] = 'localhost'
    config['database.port'] = 5432
    config['database.pool_size'] = 10
    config['database.timeout'] = 30

    # Cache settings
    config['cache.enabled'] = True
    config['cache.ttl'] = 3600
    config['cache.max_size'] = 1000

    # API settings
    config['api.rate_limit'] = 100  # requests per minute
    config['api.timeout'] = 5
    config['api.max_retries'] = 3

    print(f"\n✅ Initial config loaded: {len(config)} settings configured")

    # ========================================================================
    # SCENARIO 2: Creating a Snapshot Before Deployment
    # ========================================================================
    print("\n\n📸 Step 2: Creating snapshot before production deployment")
    print("-" * 70)

    # Always create snapshot before risky changes
    pre_deployment_snapshot = config.snapshot()
    print("✅ Snapshot created - can rollback if deployment fails")

    # ========================================================================
    # SCENARIO 3: Deploying New Configuration
    # ========================================================================
    print("\n\n🚀 Step 3: Deploying new configuration for performance upgrade")
    print("-" * 70)

    # Increase database pool for better performance
    config['database.pool_size'] = 50
    config['database.timeout'] = 60

    # Enable more aggressive caching
    config['cache.ttl'] = 7200
    config['cache.max_size'] = 5000

    # Increase API rate limits
    config['api.rate_limit'] = 500

    print("✅ New configuration deployed")
    print("\nCurrent configuration:")
    for key, value in sorted(config.latest().items()):
        print(f"  {key}: {value}")

    # ========================================================================
    # SCENARIO 4: Monitoring Shows Issues - Rollback Needed
    # ========================================================================
    print("\n\n⚠️  Step 4: Production issues detected - rolling back!")
    print("-" * 70)
    print("❌ Error: Database connections exhausted")
    print("❌ Error: API rate limit causing client failures")

    # Instant rollback to pre-deployment snapshot
    config.rollback(pre_deployment_snapshot)
    print("\n✅ Rolled back to previous stable configuration")

    print("\nRestored configuration:")
    for key, value in sorted(config.latest().items()):
        print(f"  {key}: {value}")

    # ========================================================================
    # SCENARIO 5: Viewing Configuration History
    # ========================================================================
    print("\n\n📊 Step 5: Analyzing configuration history")
    print("-" * 70)

    # Check how database pool size changed over time
    db_pool_history = config.history('database.pool_size')
    print(f"\nDatabase pool_size changes ({len(db_pool_history)} versions):")
    for timestamp, value in db_pool_history:
        when = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  {when}: {value}")

    # ========================================================================
    # SCENARIO 6: Using Context Manager for Safe Bulk Updates
    # ========================================================================
    print("\n\n🔧 Step 6: Safe bulk update with automatic rollback on error")
    print("-" * 70)

    try:
        # Context manager automatically rolls back if exception occurs
        with config.snapshot_context():
            print("Attempting risky bulk configuration update...")

            # Update multiple settings at once
            config.put_many({
                'database.pool_size': 100,
                'cache.ttl': 10800,
                'api.rate_limit': 1000,
                'new_feature.enabled': True
            })

            # Simulate validation failure
            print("Running configuration validation...")
            # Uncomment next line to see automatic rollback:
            # raise ValueError("Validation failed: pool_size too high!")

            print("✅ Bulk update successful")

    except ValueError as e:
        print(f"❌ Update failed: {e}")
        print("✅ Automatically rolled back to previous state")

    # ========================================================================
    # SCENARIO 7: Temporary Feature Flags with TTL
    # ========================================================================
    print("\n\n🚩 Step 7: Temporary feature flag (auto-expires in 2 seconds)")
    print("-" * 70)

    # Enable beta feature for 2 seconds (useful for testing)
    config.put('beta_feature.enabled', True, ttl=2)
    print(f"Beta feature enabled: {config.get('beta_feature.enabled')}")

    # Wait for expiration
    import time
    time.sleep(2.5)

    print(f"After 2 seconds: {config.get('beta_feature.enabled', default='expired')}")

    # ========================================================================
    # SCENARIO 8: Querying Configuration
    # ========================================================================
    print("\n\n🔍 Step 8: Advanced configuration queries")
    print("-" * 70)

    # Find all database-related settings
    db_settings = config.query(lambda k, v: k.startswith('database.'))
    print("\nAll database settings:")
    for key, value in db_settings.items():
        print(f"  {key}: {value}")

    # Find all settings with numeric values over 50
    high_value_settings = config.query(lambda k, v: isinstance(v, int) and v > 50)
    print("\nSettings with values > 50:")
    for key, value in high_value_settings.items():
        print(f"  {key}: {value}")

    # ========================================================================
    # SCENARIO 9: Exporting Configuration
    # ========================================================================
    print("\n\n💾 Step 9: Exporting configuration to file")
    print("-" * 70)

    # Export current configuration to JSON for backup
    current_config = config.latest()
    with open('/tmp/config_backup.json', 'w') as f:
        json.dump(current_config, f, indent=2)
    print("✅ Configuration exported to /tmp/config_backup.json")

    # Save complete ChronoMap with history (compressed)
    config.save_pickle('/tmp/config_with_history.pkl', compress='lzma')
    print("✅ Full configuration history saved (compressed)")

    # ========================================================================
    # SCENARIO 10: Viewing Audit Log
    # ========================================================================
    print("\n\n📜 Step 10: Configuration audit log")
    print("-" * 70)

    print(f"\nTotal configuration changes: {len(audit_log)}")
    print("\nRecent changes:")
    for entry in audit_log[-5:]:  # Last 5 changes
        print(f"  [{entry['timestamp']}] {entry['setting']}")
        print(f"    {entry['old_value']} → {entry['new_value']}")

    # ========================================================================
    # Statistics
    # ========================================================================
    print("\n\n📊 Configuration System Statistics")
    print("-" * 70)

    stats = config.get_stats()
    print(f"Total reads: {stats['reads']}")
    print(f"Total writes: {stats['writes']}")
    print(f"Cache hit rate: {stats.get('cache_hit_rate', 0):.1f}%")
    print(f"Snapshots created: {stats['snapshots']}")
    print(f"Active settings: {stats['total_keys']}")
    print(f"Total version history: {stats['total_versions']}")

    print("\n" + "=" * 70)
    print("✅ Configuration Version Control Demo Complete!")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("• ChronoMap provides instant rollback for failed deployments")
    print("• Audit logs track every configuration change")
    print("• Context managers ensure safe bulk updates")
    print("• TTL enables temporary feature flags")
    print("• Query capabilities help analyze configurations")
    print("\nTry modifying this script to manage your own application configs!")
    print("=" * 70)


if __name__ == '__main__':
    main()
