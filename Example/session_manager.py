"""
User Session Manager with Auto-Expiration
==========================================

This example shows how to build a session management system using ChronoMap
with automatic TTL cleanup, session analytics, and security features.

Perfect for:
- Web application session storage
- Managing user login sessions with auto-logout
- Tracking session activity and user behavior
- Security monitoring (concurrent sessions, suspicious activity)

Run this script: python session_manager.py
"""

from chronomap import ChronoMap
from datetime import datetime, timedelta
import random
import string
import time


def generate_session_token(length=32):
    """Generate a secure random session token"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def main():
    print("=" * 70)
    print("User Session Manager with ChronoMap")
    print("=" * 70)
    print()

    # Initialize session store with automatic TTL cleanup
    # Sessions are automatically removed after expiration
    # ttl_cleanup_interval=5 runs cleanup every 5 seconds
    sessions = ChronoMap(
        enable_ttl_cleanup=True,
        ttl_cleanup_interval=5,  # Check for expired sessions every 5 seconds
        cache_size=500,  # Cache frequently accessed sessions
        max_history=10   # Keep last 10 versions of each session
    )

    # Track session events for analytics
    session_events = []

    def log_session_event(key, old_value, new_value, timestamp):
        """Track all session changes for analytics"""
        if key.startswith('session:'):
            session_id = key.split(':')[1]
            event = {
                'session_id': session_id,
                'timestamp': datetime.fromtimestamp(timestamp),
                'event': 'created' if old_value is None else 'updated',
                'data': new_value
            }
            session_events.append(event)

    sessions.on_change(log_session_event)

    # ========================================================================
    # SCENARIO 1: User Login - Create Session
    # ========================================================================
    print("👤 Step 1: User login - creating sessions")
    print("-" * 70)

    # Simulate 3 users logging in
    users = [
        {'user_id': 101, 'username': 'alice', 'role': 'admin'},
        {'user_id': 102, 'username': 'bob', 'role': 'user'},
        {'user_id': 103, 'username': 'charlie', 'role': 'user'}
    ]

    user_sessions = {}  # Map user_id to session_token

    for user in users:
        # Generate unique session token
        token = generate_session_token()

        # Store session data with 30-second TTL (normally would be 30 minutes)
        # Using 30 seconds for demo purposes to show auto-expiration
        session_data = {
            'user_id': user['user_id'],
            'username': user['username'],
            'role': user['role'],
            'login_time': datetime.now().isoformat(),
            'ip_address': f'192.168.1.{random.randint(1, 255)}',
            'user_agent': 'Mozilla/5.0 (Demo Browser)',
            'last_activity': datetime.now().isoformat()
        }

        sessions.put(
            f"session:{token}",
            session_data,
            ttl=30  # Session expires in 30 seconds
        )

        user_sessions[user['user_id']] = token
        print(f"✅ {user['username']} logged in")
        print(f"   Token: {token[:16]}...")
        print(f"   Expires in: 30 seconds")

    print(f"\n📊 Active sessions: {len(sessions)}")

    # ========================================================================
    # SCENARIO 2: Session Validation & Activity Tracking
    # ========================================================================
    print("\n\n🔐 Step 2: Validating sessions and tracking activity")
    print("-" * 70)

    def validate_session(token):
        """Check if session is valid (exists and not expired)"""
        session_key = f"session:{token}"
        session_data = sessions.get(session_key)

        if session_data is None:
            return None, "Session not found or expired"

        return session_data, "Valid session"

    # Check Alice's session
    alice_token = user_sessions[101]
    session_data, status = validate_session(alice_token)

    if session_data:
        print(f"✅ Session valid for: {session_data['username']}")
        print(f"   Role: {session_data['role']}")
        print(f"   Login time: {session_data['login_time']}")

        # Update last activity time
        session_data['last_activity'] = datetime.now().isoformat()
        sessions.put(
            f"session:{alice_token}",
            session_data,
            ttl=30  # Refresh TTL on activity
        )
        print("   ⏰ Session TTL refreshed")
    else:
        print(f"❌ {status}")

    # ========================================================================
    # SCENARIO 3: Querying Active Sessions
    # ========================================================================
    print("\n\n🔍 Step 3: Analyzing active sessions")
    print("-" * 70)

    # Find all admin sessions
    admin_sessions = sessions.query(
        lambda k, v: k.startswith('session:') and v.get('role') == 'admin'
    )
    print(f"\n👑 Admin sessions: {len(admin_sessions)}")
    for key, data in admin_sessions.items():
        print(f"   • {data['username']} (ID: {data['user_id']})")

    # Find all sessions from specific IP range
    local_sessions = sessions.query(
        lambda k, v: k.startswith('session:') and v.get('ip_address', '').startswith('192.168')
    )
    print(f"\n🌐 Local network sessions: {len(local_sessions)}")

    # Count total active sessions
    total_active = sessions.count(lambda k, v: k.startswith('session:'))
    print(f"\n📊 Total active sessions: {total_active}")

    # ========================================================================
    # SCENARIO 4: Detecting Multiple Sessions for Same User
    # ========================================================================
    print("\n\n🚨 Step 4: Security - detecting multiple sessions per user")
    print("-" * 70)

    # Simulate Alice logging in again from different location
    new_token = generate_session_token()
    duplicate_session = {
        'user_id': 101,
        'username': 'alice',
        'role': 'admin',
        'login_time': datetime.now().isoformat(),
        'ip_address': '203.0.113.42',  # Different IP
        'user_agent': 'Mozilla/5.0 (Mobile Browser)',
        'last_activity': datetime.now().isoformat()
    }

    sessions.put(f"session:{new_token}", duplicate_session, ttl=30)
    print(f"⚠️  Alice logged in from new location")

    # Find all sessions for user 101
    alice_sessions = sessions.query(
        lambda k, v: k.startswith('session:') and v.get('user_id') == 101
    )

    print(f"\n🔍 User alice has {len(alice_sessions)} active sessions:")
    for key, data in alice_sessions.items():
        token = key.split(':')[1]
        print(f"   • {token[:16]}... from {data['ip_address']}")

    # Security policy: Limit to 2 sessions per user
    if len(alice_sessions) > 2:
        print("\n⚠️  Security alert: Too many concurrent sessions!")

    # ========================================================================
    # SCENARIO 5: Session History & Audit Trail
    # ========================================================================
    print("\n\n📜 Step 5: Viewing session history (audit trail)")
    print("-" * 70)

    # Get history of Alice's first session
    history = sessions.history(f"session:{alice_token}")
    print(f"\nSession activity log ({len(history)} events):")

    for timestamp, data in history:
        when = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
        activity = data.get('last_activity', 'N/A')
        print(f"   [{when}] Last activity: {activity}")

    # ========================================================================
    # SCENARIO 6: Manual Session Logout
    # ========================================================================
    print("\n\n👋 Step 6: Manual logout - terminating session")
    print("-" * 70)

    # Bob logs out
    bob_token = user_sessions[102]
    bob_data = sessions.get(f"session:{bob_token}")

    if bob_data:
        print(f"Logging out user: {bob_data['username']}")
        sessions.delete(f"session:{bob_token}")
        print("✅ Session terminated")

        # Verify session is gone
        verify = sessions.get(f"session:{bob_token}")
        print(f"Session still exists: {verify is not None}")

    # ========================================================================
    # SCENARIO 7: Waiting for Auto-Expiration
    # ========================================================================
    print("\n\n⏳ Step 7: Demonstrating auto-expiration")
    print("-" * 70)
    print("Waiting for sessions to expire (30 seconds)...")
    print("Background cleanup thread will remove expired sessions...")

    # Check session count every 5 seconds
    for i in range(7):  # 35 seconds total
        time.sleep(5)
        active_count = sessions.count(lambda k, v: k.startswith('session:'))
        elapsed = (i + 1) * 5
        print(f"   [{elapsed}s] Active sessions: {active_count}")

        if active_count == 0:
            print("\n✅ All sessions automatically expired and cleaned up!")
            break

    # ========================================================================
    # SCENARIO 8: Session Analytics
    # ========================================================================
    print("\n\n📊 Step 8: Session analytics from event log")
    print("-" * 70)

    print(f"\nTotal session events captured: {len(session_events)}")

    # Count events by type
    created_count = sum(1 for e in session_events if e['event'] == 'created')
    updated_count = sum(1 for e in session_events if e['event'] == 'updated')

    print(f"• Sessions created: {created_count}")
    print(f"• Session updates: {updated_count}")

    # Show recent events
    print("\nRecent session events:")
    for event in session_events[-5:]:
        time_str = event['timestamp'].strftime('%H:%M:%S')
        user = event['data'].get('username', 'unknown')
        print(f"   [{time_str}] {event['event'].upper()}: {user}")

    # ========================================================================
    # SCENARIO 9: Session Statistics
    # ========================================================================
    print("\n\n📈 Step 9: ChronoMap performance statistics")
    print("-" * 70)

    stats = sessions.get_stats()
    print(f"Total session reads: {stats['reads']}")
    print(f"Total session writes: {stats['writes']}")
    print(f"Session deletions: {stats['deletes']}")
    print(f"Cache hit rate: {stats.get('cache_hit_rate', 0):.1f}%")
    print(f"Background cleanups: {stats.get('ttl_cleanup_count', 0)}")

    # ========================================================================
    # SCENARIO 10: Best Practices Summary
    # ========================================================================
    print("\n\n" + "=" * 70)
    print("✅ Session Manager Demo Complete!")
    print("=" * 70)
    print("\n💡 Key Features Demonstrated:")
    print("• Automatic session expiration with TTL")
    print("• Background cleanup thread removes expired sessions")
    print("• Session validation and activity tracking")
    print("• Security monitoring (multiple sessions, suspicious activity)")
    print("• Complete audit trail of all session events")
    print("• High-performance caching for frequently accessed sessions")
    print("\n🔧 Production Tips:")
    print("• Use longer TTLs in production (30-60 minutes)")
    print("• Store session tokens in HTTP-only cookies")
    print("• Implement CSRF tokens for additional security")
    print("• Log session events to external monitoring system")
    print("• Consider Redis or database for distributed sessions")
    print("\n📝 ChronoMap Advantages:")
    print("• Zero external dependencies (no Redis setup needed)")
    print("• Built-in session history for debugging")
    print("• Automatic cleanup prevents memory leaks")
    print("• Perfect for small-to-medium applications")
    print("=" * 70)


if __name__ == '__main__':
    main()
