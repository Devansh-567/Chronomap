"""
Feature Flag Manager with A/B Testing
======================================

This example shows how to use ChronoMap for feature flag management,
A/B testing, gradual rollouts, and safe deployments with instant rollback.

Perfect for:
- Enabling/disabling features without code deployment
- A/B testing different features on user segments
- Gradual rollout (canary deployments)
- Emergency kill switches for problematic features
- Testing features in staging before production

Run this script: python feature_flags.py
"""

from chronomap import ChronoMap
from datetime import datetime, timedelta
import random
import tempfile
import os
import json


class FeatureFlagManager:
    """
    Feature flag manager built on ChronoMap with A/B testing capabilities
    """

    def __init__(self):
        # Initialize flag store with history tracking
        self.flags = ChronoMap(
            max_history=100,  # Keep history of flag changes
            cache_size=200,   # Cache frequently checked flags
            enable_ttl_cleanup=False
        )

        # Track flag evaluation history for analytics
        self.evaluations = []

    def create_flag(self, flag_name, default_value=False, description=""):
        """Create a new feature flag"""
        flag_data = {
            'enabled': default_value,
            'description': description,
            'rollout_percentage': 0 if not default_value else 100,
            'target_users': [],
            'target_groups': [],
            'created_at': datetime.now().isoformat()
        }
        self.flags.put(flag_name, flag_data)
        return flag_data

    def is_enabled(self, flag_name, user_id=None, user_group=None):
        """
        Check if a feature flag is enabled for a given user/group

        Uses consistent hashing for A/B testing - same user always gets same result
        """
        flag_data = self.flags.get(flag_name)

        if flag_data is None:
            # Flag doesn't exist - default to False
            return False

        # Track evaluation for analytics
        self.evaluations.append({
            'flag': flag_name,
            'user_id': user_id,
            'user_group': user_group,
            'timestamp': datetime.now(),
            'result': None  # Will be set below
        })

        # Check if explicitly enabled for specific users
        if user_id and user_id in flag_data.get('target_users', []):
            self.evaluations[-1]['result'] = True
            return True

        # Check if enabled for specific groups
        if user_group and user_group in flag_data.get('target_groups', []):
            self.evaluations[-1]['result'] = True
            return True

        # Check global enable/disable
        if not flag_data.get('enabled', False):
            self.evaluations[-1]['result'] = False
            return False

        # Check rollout percentage (for gradual rollout)
        rollout_pct = flag_data.get('rollout_percentage', 100)

        if rollout_pct >= 100:
            self.evaluations[-1]['result'] = True
            return True

        if rollout_pct <= 0:
            self.evaluations[-1]['result'] = False
            return False

        # Use consistent hashing for A/B testing
        # Same user_id always gets same result
        if user_id:
            hash_value = hash(f"{flag_name}:{user_id}") % 100
            result = hash_value < rollout_pct
            self.evaluations[-1]['result'] = result
            return result

        # Random for anonymous users
        result = random.randint(0, 99) < rollout_pct
        self.evaluations[-1]['result'] = result
        return result

    def enable_flag(self, flag_name, rollout_percentage=100):
        """Enable a flag with optional gradual rollout"""
        flag_data = self.flags.get(flag_name, {})
        flag_data['enabled'] = True
        flag_data['rollout_percentage'] = rollout_percentage
        self.flags.put(flag_name, flag_data)

    def disable_flag(self, flag_name):
        """Disable a flag (emergency kill switch)"""
        flag_data = self.flags.get(flag_name, {})
        flag_data['enabled'] = False
        flag_data['rollout_percentage'] = 0
        self.flags.put(flag_name, flag_data)

    def set_rollout_percentage(self, flag_name, percentage):
        """Adjust rollout percentage for gradual deployment"""
        flag_data = self.flags.get(flag_name, {})
        flag_data['rollout_percentage'] = percentage
        self.flags.put(flag_name, flag_data)

    def target_users(self, flag_name, user_ids):
        """Enable flag for specific users (beta testers)"""
        flag_data = self.flags.get(flag_name, {})
        flag_data['target_users'] = user_ids
        self.flags.put(flag_name, flag_data)

    def target_groups(self, flag_name, groups):
        """Enable flag for specific user groups (e.g., 'beta', 'internal')"""
        flag_data = self.flags.get(flag_name, {})
        flag_data['target_groups'] = groups
        self.flags.put(flag_name, flag_data)

    def get_flag_history(self, flag_name):
        """Get complete history of flag changes"""
        return self.flags.history(flag_name)

    def get_evaluation_stats(self, flag_name):
        """Get statistics on flag evaluations"""
        flag_evals = [e for e in self.evaluations if e['flag'] == flag_name]

        if not flag_evals:
            return None

        total = len(flag_evals)
        enabled_count = sum(1 for e in flag_evals if e['result'])

        return {
            'total_evaluations': total,
            'enabled_count': enabled_count,
            'disabled_count': total - enabled_count,
            'enabled_percentage': (enabled_count / total * 100) if total > 0 else 0
        }


def main():
    print("=" * 70)
    print("Feature Flag Manager with A/B Testing")
    print("=" * 70)
    print()

    # Initialize feature flag manager
    ff = FeatureFlagManager()

    # ========================================================================
    # SCENARIO 1: Creating Feature Flags
    # ========================================================================
    print("🚩 Step 1: Creating feature flags")
    print("-" * 70)

    # Create various feature flags
    ff.create_flag(
        'new_ui_design',
        default_value=False,
        description='New redesigned user interface'
    )

    ff.create_flag(
        'advanced_analytics',
        default_value=False,
        description='Advanced analytics dashboard'
    )

    ff.create_flag(
        'ai_recommendations',
        default_value=False,
        description='AI-powered product recommendations'
    )

    ff.create_flag(
        'dark_mode',
        default_value=True,  # Fully rolled out
        description='Dark mode theme'
    )

    print("✅ Created 4 feature flags")
    print("\nAll flags:")
    for flag_name in ff.flags.keys():
        flag_data = ff.flags.get(flag_name)
        status = "🟢 Enabled" if flag_data['enabled'] else "🔴 Disabled"
        print(f"   {status} {flag_name}")
        print(f"      {flag_data['description']}")

    # ========================================================================
    # SCENARIO 2: Beta Testing - Target Specific Users
    # ========================================================================
    print("\n\n👥 Step 2: Beta testing - enabling for specific users")
    print("-" * 70)

    # Enable new UI for beta testers only
    beta_testers = [101, 102, 103]  # User IDs of beta testers
    ff.target_users('new_ui_design', beta_testers)
    ff.enable_flag('new_ui_design', rollout_percentage=0)  # Only for targeted users

    print(f"✅ Enabled 'new_ui_design' for beta testers: {beta_testers}")

    # Test flag evaluation for different users
    test_users = [101, 104, 105]  # 101 is beta tester, others aren't

    print("\nTesting flag for different users:")
    for user_id in test_users:
        is_enabled = ff.is_enabled('new_ui_design', user_id=user_id)
        status = "✅" if is_enabled else "❌"
        user_type = "Beta tester" if user_id in beta_testers else "Regular user"
        print(f"   {status} User {user_id} ({user_type}): {is_enabled}")

    # ========================================================================
    # SCENARIO 3: Group-Based Rollout
    # ========================================================================
    print("\n\n🏢 Step 3: Group-based rollout (internal users first)")
    print("-" * 70)

    # Enable advanced analytics for internal team
    ff.target_groups('advanced_analytics', ['internal', 'qa_team'])
    ff.enable_flag('advanced_analytics')

    print("✅ Enabled 'advanced_analytics' for groups: internal, qa_team")

    # Test for different user groups
    test_scenarios = [
        (201, 'internal'),
        (202, 'customer'),
        (203, 'qa_team'),
        (204, 'customer')
    ]

    print("\nTesting flag for different user groups:")
    for user_id, group in test_scenarios:
        is_enabled = ff.is_enabled('advanced_analytics', user_id=user_id, user_group=group)
        status = "✅" if is_enabled else "❌"
        print(f"   {status} User {user_id} (group: {group}): {is_enabled}")

    # ========================================================================
    # SCENARIO 4: Gradual Rollout (Canary Deployment)
    # ========================================================================
    print("\n\n📊 Step 4: Gradual rollout - 10% -> 50% -> 100%")
    print("-" * 70)

    # Start with 10% rollout
    print("\n🔵 Phase 1: 10% rollout")
    ff.enable_flag('ai_recommendations', rollout_percentage=10)

    # Simulate 100 users checking the flag
    enabled_count = 0
    for i in range(100):
        if ff.is_enabled('ai_recommendations', user_id=i):
            enabled_count += 1

    print(f"   {enabled_count}/100 users got the new feature (~10% expected)")

    # Increase to 50%
    print("\n🟡 Phase 2: Increasing to 50%")
    ff.set_rollout_percentage('ai_recommendations', 50)

    enabled_count = 0
    for i in range(100):
        if ff.is_enabled('ai_recommendations', user_id=i):
            enabled_count += 1

    print(f"   {enabled_count}/100 users got the new feature (~50% expected)")

    # Full rollout
    print("\n🟢 Phase 3: Full rollout (100%)")
    ff.set_rollout_percentage('ai_recommendations', 100)

    enabled_count = 0
    for i in range(100):
        if ff.is_enabled('ai_recommendations', user_id=i):
            enabled_count += 1

    print(f"   {enabled_count}/100 users got the new feature (100% expected)")

    # ========================================================================
    # SCENARIO 5: A/B Testing Consistency
    # ========================================================================
    print("\n\n🧪 Step 5: A/B testing - consistent user experience")
    print("-" * 70)

    # Set 50% rollout for A/B test
    ff.set_rollout_percentage('ai_recommendations', 50)

    # Check same user multiple times - should always get same result
    test_user_id = 42
    print(f"\nChecking flag for user {test_user_id} multiple times:")

    results = []
    for i in range(5):
        is_enabled = ff.is_enabled('ai_recommendations', user_id=test_user_id)
        results.append(is_enabled)
        print(f"   Check {i+1}: {is_enabled}")

    # Verify consistency
    if len(set(results)) == 1:
        print("\n✅ Consistent! Same user always gets same experience")
    else:
        print("\n❌ Inconsistent! This shouldn't happen")

    # ========================================================================
    # SCENARIO 6: Emergency Kill Switch
    # ========================================================================
    print("\n\n🚨 Step 6: Emergency kill switch - disabling problematic feature")
    print("-" * 70)

    print("⚠️  Simulating: Bug found in 'ai_recommendations'")
    print("🔴 Activating kill switch...")

    # Take snapshot before disabling (for audit trail)
    snapshot = ff.flags.snapshot()

    # Immediately disable the feature
    ff.disable_flag('ai_recommendations')

    print("✅ Feature disabled for all users")

    # Verify it's disabled
    test_results = [
        ff.is_enabled('ai_recommendations', user_id=i)
        for i in range(10)
    ]

    if not any(test_results):
        print("✅ Verified: Feature disabled for all tested users")

    # ========================================================================
    # SCENARIO 7: Flag Change History (Audit Trail)
    # ========================================================================
    print("\n\n📜 Step 7: Viewing flag change history")
    print("-" * 70)

    # Get history of ai_recommendations flag
    history = ff.get_flag_history('ai_recommendations')

    print(f"\n'ai_recommendations' change history ({len(history)} changes):")
    for timestamp, flag_data in history:
        when = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
        enabled = flag_data.get('enabled', False)
        rollout = flag_data.get('rollout_percentage', 0)
        status = "🟢" if enabled else "🔴"
        print(f"   [{when}] {status} Enabled={enabled}, Rollout={rollout}%")

    # ========================================================================
    # SCENARIO 8: Rollback to Previous State
    # ========================================================================
    print("\n\n⏮️  Step 8: Rolling back flag configuration")
    print("-" * 70)

    print("Bug fixed! Re-enabling 'ai_recommendations' to 50%")

    # Rollback to snapshot (or manually restore)
    ff.flags.rollback(snapshot)

    # Check restored state
    flag_data = ff.flags.get('ai_recommendations')
    print(f"✅ Restored state:")
    print(f"   Enabled: {flag_data['enabled']}")
    print(f"   Rollout: {flag_data['rollout_percentage']}%")

    # ========================================================================
    # SCENARIO 9: Flag Evaluation Analytics
    # ========================================================================
    print("\n\n📊 Step 9: Flag evaluation analytics")
    print("-" * 70)

    # Get statistics for each flag
    all_flags = list(ff.flags.keys())

    print("\nFlag evaluation statistics:")
    for flag_name in all_flags:
        stats = ff.get_evaluation_stats(flag_name)
        if stats:
            print(f"\n📊 {flag_name}:")
            print(f"   Total checks: {stats['total_evaluations']}")
            print(f"   Enabled: {stats['enabled_count']} ({stats['enabled_percentage']:.1f}%)")
            print(f"   Disabled: {stats['disabled_count']}")

    # ========================================================================
    # SCENARIO 10: Current Flag Status Dashboard
    # ========================================================================
    print("\n\n🎛️  Step 10: Feature flag dashboard")
    print("-" * 70)

    print("\nCurrent feature flag status:")
    print("-" * 60)
    print(f"{'Flag Name':<25} {'Status':<12} {'Rollout':<10} {'Targets'}")
    print("-" * 60)

    for flag_name in all_flags:
        flag_data = ff.flags.get(flag_name)

        status = "🟢 Enabled" if flag_data['enabled'] else "🔴 Disabled"
        rollout = f"{flag_data['rollout_percentage']}%"

        targets = []
        if flag_data.get('target_users'):
            targets.append(f"{len(flag_data['target_users'])} users")
        if flag_data.get('target_groups'):
            targets.append(f"{len(flag_data['target_groups'])} groups")

        target_str = ", ".join(targets) if targets else "All users"

        print(f"{flag_name:<25} {status:<12} {rollout:<10} {target_str}")

    # ========================================================================
    # SCENARIO 11: Exporting Flag Configuration
    # ========================================================================
    print("\n\n💾 Step 11: Exporting flag configuration")
    print("-" * 70)

    # Get temp directory (cross-platform)
    temp_dir = tempfile.gettempdir()

    # Export to JSON for documentation
    flag_export = {}
    for flag_name in all_flags:
        flag_data = ff.flags.get(flag_name)
        flag_export[flag_name] = flag_data

    flags_json_path = os.path.join(temp_dir, 'feature_flags.json')
    with open(flags_json_path, 'w') as f:
        json.dump(flag_export, f, indent=2)

    print(f"✅ Flag configuration exported to {flags_json_path}")

    # Save full history
    flags_pkl_path = os.path.join(temp_dir, 'feature_flags_history.pkl')
    ff.flags.save_pickle(flags_pkl_path, compress='lzma')
    print(f"✅ Flag history saved to {flags_pkl_path}")

    # ========================================================================
    # Summary
    # ========================================================================
    print("\n\n" + "=" * 70)
    print("✅ Feature Flag Management Demo Complete!")
    print("=" * 70)
    print("\n💡 Key Features Demonstrated:")
    print("• Creating and managing feature flags")
    print("• Beta testing with targeted users")
    print("• Group-based rollout (internal teams first)")
    print("• Gradual rollout (10% -> 50% -> 100%)")
    print("• A/B testing with consistent user experience")
    print("• Emergency kill switches for quick rollback")
    print("• Complete audit trail of all flag changes")
    print("• Flag evaluation analytics")
    print("\n🔧 Production Use Cases:")
    print("• Safe feature deployment without code changes")
    print("• A/B testing different features on user segments")
    print("• Canary deployments with gradual rollout")
    print("• Quick emergency feature disable")
    print("• Beta testing with selected users")
    print("\n📝 ChronoMap Advantages:")
    print("• Built-in history tracking (audit compliance)")
    print("• Instant rollback with snapshots")
    print("• No external dependencies (vs LaunchDarkly, Split.io)")
    print("• Perfect for small-to-medium applications")
    print("• Easy integration with existing Python apps")
    print("\n💡 Production Tips:")
    print("• Use environment-specific flag stores (dev, staging, prod)")
    print("• Implement flag evaluation caching for high-traffic apps")
    print("• Set up monitoring alerts for flag changes")
    print("• Document flag purpose and rollback procedures")
    print("• Clean up old flags after full rollout")
    print("=" * 70)


if __name__ == '__main__':
    main()
