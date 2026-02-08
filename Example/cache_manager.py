"""
Intelligent Cache Manager with Time-Based Invalidation
=======================================================

This example demonstrates using ChronoMap as a smart caching layer with
TTL expiration, version tracking, and cache analytics.

Perfect for:
- API response caching with auto-expiration
- Database query result caching
- Expensive computation result caching
- Cache warmup and preloading strategies
- Cache invalidation patterns

Run this script: python cache_manager.py
"""

from chronomap import ChronoMap
from datetime import datetime, timedelta
import time
import random
import hashlib


class IntelligentCache:
    """
    Smart cache manager built on ChronoMap with TTL and analytics
    """

    def __init__(self, default_ttl=300, enable_stats=True):
        """
        Initialize cache manager

        Args:
            default_ttl: Default time-to-live in seconds (5 minutes)
            enable_stats: Track cache hit/miss statistics
        """
        self.cache = ChronoMap(
            enable_ttl_cleanup=True,
            ttl_cleanup_interval=10,  # Cleanup every 10 seconds
            cache_size=1000,  # LRU cache for hot keys
            max_history=5     # Keep last 5 cached values per key
        )

        self.default_ttl = default_ttl
        self.enable_stats = enable_stats

        # Track cache performance
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'invalidations': 0,
            'expirations': 0
        }

    def _generate_key(self, namespace, key_parts):
        """Generate cache key from namespace and key parts"""
        if isinstance(key_parts, (list, tuple)):
            key_str = ':'.join(str(p) for p in key_parts)
        else:
            key_str = str(key_parts)

        return f"{namespace}:{key_str}"

    def get(self, namespace, key_parts, default=None):
        """
        Get value from cache

        Args:
            namespace: Cache namespace (e.g., 'user', 'product', 'api')
            key_parts: Key identifier (can be single value or list)
            default: Value to return if not found

        Returns:
            Cached value or default
        """
        cache_key = self._generate_key(namespace, key_parts)
        value = self.cache.get(cache_key, default=default)

        if value is None or value == default:
            self.stats['misses'] += 1
            return default
        else:
            self.stats['hits'] += 1
            return value

    def set(self, namespace, key_parts, value, ttl=None):
        """
        Set value in cache with optional TTL

        Args:
            namespace: Cache namespace
            key_parts: Key identifier
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        cache_key = self._generate_key(namespace, key_parts)
        ttl = ttl if ttl is not None else self.default_ttl

        self.cache.put(cache_key, value, ttl=ttl)
        self.stats['sets'] += 1

    def invalidate(self, namespace, key_parts=None):
        """
        Invalidate cache entries

        Args:
            namespace: Cache namespace
            key_parts: Specific key to invalidate (None = all in namespace)
        """
        if key_parts is not None:
            # Invalidate specific key
            cache_key = self._generate_key(namespace, key_parts)
            if self.cache.delete(cache_key):
                self.stats['invalidations'] += 1
        else:
            # Invalidate entire namespace
            prefix = f"{namespace}:"
            keys_to_delete = [
                k for k in self.cache.keys()
                if str(k).startswith(prefix)
            ]

            for key in keys_to_delete:
                self.cache.delete(key)
                self.stats['invalidations'] += 1

    def get_or_compute(self, namespace, key_parts, compute_func, ttl=None):
        """
        Get from cache or compute if missing (cache-aside pattern)

        Args:
            namespace: Cache namespace
            key_parts: Key identifier
            compute_func: Function to call if cache miss
            ttl: TTL for newly computed value

        Returns:
            Cached or computed value
        """
        # Try cache first
        value = self.get(namespace, key_parts)

        if value is not None:
            return value

        # Cache miss - compute value
        value = compute_func()

        # Store in cache
        self.set(namespace, key_parts, value, ttl=ttl)

        return value

    def warmup(self, namespace, key_value_pairs, ttl=None):
        """
        Pre-populate cache (cache warmup)

        Args:
            namespace: Cache namespace
            key_value_pairs: Dict of key -> value pairs
            ttl: TTL for all entries
        """
        for key_parts, value in key_value_pairs.items():
            self.set(namespace, key_parts, value, ttl=ttl)

    def get_stats(self):
        """Get cache performance statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0

        chrono_stats = self.cache.get_stats()

        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': hit_rate,
            'sets': self.stats['sets'],
            'invalidations': self.stats['invalidations'],
            'active_entries': chrono_stats['total_keys'],
            'total_versions': chrono_stats['total_versions'],
            'chronomap_cache_hit_rate': chrono_stats.get('cache_hit_rate', 0)
        }

    def list_keys(self, namespace=None):
        """List all cache keys, optionally filtered by namespace"""
        all_keys = list(self.cache.keys())

        if namespace:
            prefix = f"{namespace}:"
            return [k for k in all_keys if str(k).startswith(prefix)]

        return all_keys


# ============================================================================
# Example Functions to Cache
# ============================================================================

def expensive_computation(n):
    """Simulate expensive computation"""
    time.sleep(0.1)  # Simulate 100ms computation
    return sum(i * i for i in range(n))


def fetch_user_from_database(user_id):
    """Simulate database query"""
    time.sleep(0.05)  # Simulate 50ms database query
    return {
        'id': user_id,
        'username': f'user_{user_id}',
        'email': f'user_{user_id}@example.com',
        'role': random.choice(['admin', 'user', 'moderator'])
    }


def call_external_api(endpoint):
    """Simulate external API call"""
    time.sleep(0.2)  # Simulate 200ms API call
    return {
        'endpoint': endpoint,
        'data': random.randint(1, 1000),
        'timestamp': datetime.now().isoformat()
    }


def main():
    print("=" * 70)
    print("Intelligent Cache Manager with ChronoMap")
    print("=" * 70)
    print()

    # Initialize cache with 30-second default TTL
    cache = IntelligentCache(default_ttl=30)

    # ========================================================================
    # SCENARIO 1: Basic Caching - Cache-Aside Pattern
    # ========================================================================
    print("📦 Step 1: Basic caching with cache-aside pattern")
    print("-" * 70)

    # First call - cache miss
    print("\n1st call (cache miss - computing):")
    start = time.time()
    result1 = cache.get_or_compute(
        'computation',
        'fibonacci_1000',
        lambda: expensive_computation(1000)
    )
    duration1 = time.time() - start
    print(f"   Result: {result1}")
    print(f"   Duration: {duration1*1000:.2f}ms")

    # Second call - cache hit
    print("\n2nd call (cache hit - instant):")
    start = time.time()
    result2 = cache.get_or_compute(
        'computation',
        'fibonacci_1000',
        lambda: expensive_computation(1000)
    )
    duration2 = time.time() - start
    print(f"   Result: {result2}")
    print(f"   Duration: {duration2*1000:.2f}ms")

    speedup = duration1 / duration2
    print(f"\n⚡ Speedup: {speedup:.1f}x faster!")

    # ========================================================================
    # SCENARIO 2: User Data Caching
    # ========================================================================
    print("\n\n👤 Step 2: Caching user data from database")
    print("-" * 70)

    # Cache user data
    user_ids = [101, 102, 103]

    print("\nFetching users (first time - from database):")
    for user_id in user_ids:
        start = time.time()
        user = cache.get_or_compute(
            'user',
            user_id,
            lambda: fetch_user_from_database(user_id),
            ttl=60  # Cache for 1 minute
        )
        duration = time.time() - start
        print(f"   User {user_id}: {user['username']} ({duration*1000:.1f}ms)")

    print("\nFetching same users (from cache):")
    for user_id in user_ids:
        start = time.time()
        user = cache.get('user', user_id)
        duration = time.time() - start
        print(f"   User {user_id}: {user['username']} ({duration*1000:.3f}ms)")

    # ========================================================================
    # SCENARIO 3: API Response Caching
    # ========================================================================
    print("\n\n🌐 Step 3: Caching external API responses")
    print("-" * 70)

    endpoints = ['/api/stats', '/api/users', '/api/products']

    print("\nFirst API calls (not cached):")
    for endpoint in endpoints:
        start = time.time()
        response = cache.get_or_compute(
            'api',
            endpoint,
            lambda ep=endpoint: call_external_api(ep),
            ttl=20  # Cache for 20 seconds
        )
        duration = time.time() - start
        print(f"   {endpoint}: {duration*1000:.1f}ms")

    print("\nSubsequent API calls (cached):")
    for endpoint in endpoints:
        start = time.time()
        response = cache.get('api', endpoint)
        duration = time.time() - start
        print(f"   {endpoint}: {duration*1000:.3f}ms")

    # ========================================================================
    # SCENARIO 4: Cache Warmup
    # ========================================================================
    print("\n\n🔥 Step 4: Cache warmup - preloading frequently accessed data")
    print("-" * 70)

    # Preload popular products
    popular_products = {
        'PROD-001': {'name': 'Laptop', 'price': 999.99, 'stock': 50},
        'PROD-002': {'name': 'Mouse', 'price': 29.99, 'stock': 200},
        'PROD-003': {'name': 'Keyboard', 'price': 79.99, 'stock': 150},
    }

    print("Warming up product cache...")
    cache.warmup('product', popular_products, ttl=120)
    print(f"✅ Preloaded {len(popular_products)} products into cache")

    # Verify instant access
    print("\nAccessing preloaded products (instant):")
    for product_id in popular_products.keys():
        product = cache.get('product', product_id)
        print(f"   {product_id}: {product['name']} - ${product['price']}")

    # ========================================================================
    # SCENARIO 5: Selective Cache Invalidation
    # ========================================================================
    print("\n\n🔄 Step 5: Cache invalidation strategies")
    print("-" * 70)

    # Update a user in database
    print("\nUser 101 updated in database - invalidating cache:")
    cache.invalidate('user', 101)
    print("✅ Cache invalidated for user 101")

    # Fetching again will hit database
    print("\nFetching user 101 again (from database):")
    start = time.time()
    user = cache.get_or_compute(
        'user',
        101,
        lambda: fetch_user_from_database(101)
    )
    duration = time.time() - start
    print(f"   {user['username']} ({duration*1000:.1f}ms)")

    # Invalidate entire namespace
    print("\n\nInvalidating all API caches:")
    cache.invalidate('api')  # No key_parts = invalidate all
    print("✅ All API caches invalidated")

    # ========================================================================
    # SCENARIO 6: Viewing Cache Contents
    # ========================================================================
    print("\n\n🔍 Step 6: Inspecting cache contents")
    print("-" * 70)

    # List all cached keys by namespace
    namespaces = ['user', 'product', 'api', 'computation']

    print("\nCache contents by namespace:")
    for namespace in namespaces:
        keys = cache.list_keys(namespace)
        print(f"   {namespace}: {len(keys)} entries")
        for key in keys[:3]:  # Show first 3
            print(f"      • {key}")

    # ========================================================================
    # SCENARIO 7: Cache History Tracking
    # ========================================================================
    print("\n\n📜 Step 7: Viewing cache entry history")
    print("-" * 70)

    # Update a product multiple times
    print("\nUpdating product PROD-001 multiple times:")
    for i in range(3):
        updated_product = {
            'name': 'Laptop',
            'price': 999.99 - (i * 50),
            'stock': 50 - (i * 10),
            'version': i + 1
        }
        cache.set('product', 'PROD-001', updated_product, ttl=60)
        print(f"   Update {i+1}: Price=${updated_product['price']}, Stock={updated_product['stock']}")
        time.sleep(0.1)

    # View history
    print("\nCache history for PROD-001:")
    history = cache.cache.history('product:PROD-001')
    for timestamp, value in history:
        when = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
        print(f"   [{when}] Price=${value['price']}, Stock={value['stock']}, v{value['version']}")

    # ========================================================================
    # SCENARIO 8: TTL Expiration Demo
    # ========================================================================
    print("\n\n⏰ Step 8: Demonstrating TTL expiration")
    print("-" * 70)

    # Set short TTL for demo
    print("Caching temp data with 3-second TTL:")
    cache.set('temp', 'short_lived', 'This expires quickly', ttl=3)
    print("   ✅ Cached: 'short_lived'")

    # Check immediately
    print("\nChecking immediately:")
    value = cache.get('temp', 'short_lived')
    print(f"   Value: {value}")

    # Wait for expiration
    print("\nWaiting 4 seconds for expiration...")
    time.sleep(4)

    # Check after expiration
    print("Checking after expiration:")
    value = cache.get('temp', 'short_lived', default='EXPIRED')
    print(f"   Value: {value}")

    # ========================================================================
    # SCENARIO 9: Cache Performance Statistics
    # ========================================================================
    print("\n\n📊 Step 9: Cache performance statistics")
    print("-" * 70)

    stats = cache.get_stats()

    print("\nCache Performance Metrics:")
    print(f"   Total requests: {stats['hits'] + stats['misses']}")
    print(f"   Cache hits: {stats['hits']}")
    print(f"   Cache misses: {stats['misses']}")
    print(f"   Hit rate: {stats['hit_rate']:.2f}%")
    print(f"   Cache sets: {stats['sets']}")
    print(f"   Invalidations: {stats['invalidations']}")
    print(f"   Active entries: {stats['active_entries']}")
    print(f"   Total versions: {stats['total_versions']}")
    print(f"   ChronoMap cache hit rate: {stats['chronomap_cache_hit_rate']:.2f}%")

    # ========================================================================
    # SCENARIO 10: Advanced Patterns
    # ========================================================================
    print("\n\n🎯 Step 10: Advanced caching patterns")
    print("-" * 70)

    # Pattern 1: Composite key caching
    print("\n1. Composite key caching (user + page):")
    cache.set('user_data', ['user_101', 'page_1'], {'content': 'Page 1 data'})
    cache.set('user_data', ['user_101', 'page_2'], {'content': 'Page 2 data'})

    page1_data = cache.get('user_data', ['user_101', 'page_1'])
    print(f"   Retrieved: {page1_data}")

    # Pattern 2: Query result caching with hash
    print("\n2. Query result caching (hash-based key):")
    query = "SELECT * FROM users WHERE role='admin'"
    query_hash = hashlib.md5(query.encode()).hexdigest()[:16]

    cache.set('query', query_hash, [{'id': 1}, {'id': 2}], ttl=30)
    print(f"   Cached query: {query[:40]}...")
    print(f"   Cache key: {query_hash}")

    # Pattern 3: Tiered caching (different TTLs)
    print("\n3. Tiered caching (different TTLs by importance):")
    cache.set('config', 'critical', {'db': 'prod'}, ttl=300)  # 5 min
    cache.set('config', 'normal', {'timeout': 30}, ttl=60)    # 1 min
    cache.set('config', 'temp', {'flag': True}, ttl=10)       # 10 sec

    print("   ✅ Critical config: 5min TTL")
    print("   ✅ Normal config: 1min TTL")
    print("   ✅ Temp config: 10sec TTL")

    # ========================================================================
    # Summary
    # ========================================================================
    print("\n\n" + "=" * 70)
    print("✅ Intelligent Cache Manager Demo Complete!")
    print("=" * 70)
    print("\n💡 Key Features Demonstrated:")
    print("• Cache-aside pattern (get-or-compute)")
    print("• TTL-based automatic expiration")
    print("• Cache warmup for frequently accessed data")
    print("• Selective cache invalidation")
    print("• Cache entry history tracking")
    print("• Performance statistics and monitoring")
    print("• Composite key support")
    print("• Tiered caching with different TTLs")
    print("\n🔧 Production Use Cases:")
    print("• API response caching")
    print("• Database query result caching")
    print("• Expensive computation result caching")
    print("• Session data caching")
    print("• Configuration caching")
    print("\n📝 ChronoMap Advantages:")
    print("• Built-in TTL with auto-cleanup")
    print("• Cache history for debugging")
    print("• No external dependencies (vs Redis)")
    print("• LRU cache on top of LRU cache (double caching!)")
    print("• Perfect for single-server applications")
    print("\n💡 Production Tips:")
    print("• Use longer TTLs for rarely changing data")
    print("• Implement cache stampede protection")
    print("• Monitor hit rates and adjust cache size")
    print("• Use namespaces to organize cache entries")
    print("• Consider write-through caching for critical data")
    print("=" * 70)


if __name__ == '__main__':
    main()
