"""
Real-Time System Metrics Collector
===================================

This example demonstrates using ChronoMap to collect and analyze system metrics
over time, similar to Prometheus or Datadog but without external dependencies.

Perfect for:
- Monitoring application performance (CPU, memory, response times)
- Collecting IoT sensor data
- Tracking business metrics (sales, user signups, API calls)
- Lightweight observability for small-to-medium projects

Run this script: python metrics_collector.py
"""

from chronomap import ChronoMap
from datetime import datetime, timedelta
import random
import time
import statistics


def simulate_cpu_usage():
    """Simulate CPU usage percentage (0-100)"""
    # Simulate realistic CPU usage with some spikes
    base = 30 + random.uniform(-10, 10)
    spike = random.randint(0, 100) < 10  # 10% chance of spike
    return min(100, base + (random.uniform(40, 60) if spike else 0))


def simulate_memory_usage():
    """Simulate memory usage in MB"""
    # Simulate slowly increasing memory with some variation
    base = 500 + random.uniform(-50, 100)
    return max(0, base)


def simulate_response_time():
    """Simulate API response time in milliseconds"""
    # Most requests are fast, occasional slow one
    if random.randint(0, 100) < 5:  # 5% slow requests
        return random.uniform(500, 2000)
    return random.uniform(10, 100)


def simulate_request_count():
    """Simulate number of requests per second"""
    hour = datetime.now().hour
    # More traffic during business hours (9-17)
    if 9 <= hour <= 17:
        return random.randint(50, 150)
    return random.randint(10, 50)


def main():
    print("=" * 70)
    print("Real-Time System Metrics Collector with ChronoMap")
    print("=" * 70)
    print()

    # Initialize metrics store
    # max_history=100 keeps last 100 data points per metric
    # cache_size=500 caches frequently queried metrics
    metrics = ChronoMap(
        max_history=100,  # Keep last 100 samples per metric
        cache_size=500,
        enable_ttl_cleanup=False  # We want to keep all metrics
    )

    # Track alerts
    alerts = []

    def check_thresholds(key, old_value, new_value, timestamp):
        """Monitor metrics and generate alerts when thresholds are exceeded"""
        # CPU alert: over 80%
        if key == 'system.cpu.usage' and new_value > 80:
            alert = {
                'timestamp': datetime.fromtimestamp(timestamp),
                'metric': key,
                'value': new_value,
                'threshold': 80,
                'severity': 'warning'
            }
            alerts.append(alert)
            print(f"⚠️  ALERT: High CPU usage: {new_value:.1f}%")

        # Memory alert: over 800 MB
        if key == 'system.memory.used_mb' and new_value > 800:
            alert = {
                'timestamp': datetime.fromtimestamp(timestamp),
                'metric': key,
                'value': new_value,
                'threshold': 800,
                'severity': 'warning'
            }
            alerts.append(alert)
            print(f"⚠️  ALERT: High memory usage: {new_value:.1f} MB")

        # Response time alert: over 1000ms
        if key == 'api.response_time_ms' and new_value > 1000:
            alert = {
                'timestamp': datetime.fromtimestamp(timestamp),
                'metric': key,
                'value': new_value,
                'threshold': 1000,
                'severity': 'critical'
            }
            alerts.append(alert)
            print(f"🚨 ALERT: Slow API response: {new_value:.1f}ms")

    # Register alert monitoring
    metrics.on_change(check_thresholds)

    # ========================================================================
    # SCENARIO 1: Collecting Metrics Over Time
    # ========================================================================
    print("📊 Step 1: Collecting system metrics (20 samples)")
    print("-" * 70)

    # Collect metrics every 0.5 seconds for 10 seconds
    collection_start = datetime.now()

    for i in range(20):
        # Collect various system metrics with timestamp
        timestamp = datetime.now()

        # System metrics
        cpu_usage = simulate_cpu_usage()
        memory_usage = simulate_memory_usage()

        # Application metrics
        response_time = simulate_response_time()
        request_count = simulate_request_count()

        # Store metrics with explicit timestamp
        metrics.put('system.cpu.usage', cpu_usage, timestamp=timestamp)
        metrics.put('system.memory.used_mb', memory_usage, timestamp=timestamp)
        metrics.put('api.response_time_ms', response_time, timestamp=timestamp)
        metrics.put('api.requests_per_sec', request_count, timestamp=timestamp)

        # Show progress
        if (i + 1) % 5 == 0:
            print(f"   Collected {i + 1}/20 samples...")

        time.sleep(0.5)  # Wait 500ms between samples

    collection_end = datetime.now()
    collection_duration = (collection_end - collection_start).total_seconds()

    print(f"\n✅ Collected 20 samples in {collection_duration:.1f} seconds")
    print(f"📊 Tracking {len(metrics)} different metrics")

    # ========================================================================
    # SCENARIO 2: Analyzing Metrics - Statistics
    # ========================================================================
    print("\n\n📈 Step 2: Calculating metric statistics")
    print("-" * 70)

    # Get CPU usage history
    cpu_history = metrics.history('system.cpu.usage')
    cpu_values = [value for _, value in cpu_history]

    print("\n🖥️  CPU Usage Statistics:")
    print(f"   Samples: {len(cpu_values)}")
    print(f"   Average: {statistics.mean(cpu_values):.2f}%")
    print(f"   Min: {min(cpu_values):.2f}%")
    print(f"   Max: {max(cpu_values):.2f}%")
    print(f"   Std Dev: {statistics.stdev(cpu_values):.2f}%")

    # Get memory usage statistics
    memory_history = metrics.history('system.memory.used_mb')
    memory_values = [value for _, value in memory_history]

    print("\n💾 Memory Usage Statistics:")
    print(f"   Samples: {len(memory_values)}")
    print(f"   Average: {statistics.mean(memory_values):.2f} MB")
    print(f"   Min: {min(memory_values):.2f} MB")
    print(f"   Max: {max(memory_values):.2f} MB")

    # Get API response time statistics
    response_time_history = metrics.history('api.response_time_ms')
    response_time_values = [value for _, value in response_time_history]

    print("\n⚡ API Response Time Statistics:")
    print(f"   Samples: {len(response_time_values)}")
    print(f"   Average: {statistics.mean(response_time_values):.2f} ms")
    print(f"   Median: {statistics.median(response_time_values):.2f} ms")
    print(f"   95th percentile: {sorted(response_time_values)[int(len(response_time_values) * 0.95)]:.2f} ms")
    print(f"   Max: {max(response_time_values):.2f} ms")

    # ========================================================================
    # SCENARIO 3: Time-Range Queries
    # ========================================================================
    print("\n\n🕐 Step 3: Querying metrics in specific time ranges")
    print("-" * 70)

    # Get CPU usage for last 5 seconds
    five_seconds_ago = datetime.now() - timedelta(seconds=5)
    recent_cpu = metrics.get_range(
        'system.cpu.usage',
        start_ts=five_seconds_ago,
        end_ts=datetime.now()
    )

    print(f"\n📊 CPU usage in last 5 seconds: {len(recent_cpu)} samples")
    if recent_cpu:
        recent_cpu_values = [value for _, value in recent_cpu]
        print(f"   Average: {statistics.mean(recent_cpu_values):.2f}%")
        print(f"   Trend: ", end="")
        if recent_cpu_values[-1] > recent_cpu_values[0]:
            print("📈 Increasing")
        else:
            print("📉 Decreasing")

    # ========================================================================
    # SCENARIO 4: Aggregation Queries
    # ========================================================================
    print("\n\n🔍 Step 4: Advanced aggregation queries")
    print("-" * 70)

    # Average of all current metric values
    all_metrics = ['system.cpu.usage', 'system.memory.used_mb',
                   'api.response_time_ms', 'api.requests_per_sec']

    print("\nCurrent metric values:")
    for metric_name in all_metrics:
        current_value = metrics.get(metric_name)
        print(f"   {metric_name}: {current_value:.2f}")

    # Calculate aggregate statistics
    def calculate_average(values):
        return sum(values) / len(values) if values else 0

    # Average CPU across time
    avg_cpu = metrics.aggregate(
        calculate_average,
        keys=['system.cpu.usage']
    )
    print(f"\n📊 Time-averaged CPU: {avg_cpu:.2f}%")

    # ========================================================================
    # SCENARIO 5: Detecting Anomalies
    # ========================================================================
    print("\n\n🔍 Step 5: Anomaly detection")
    print("-" * 70)

    # Find all samples where CPU was unusually high (> mean + 2*stdev)
    cpu_mean = statistics.mean(cpu_values)
    cpu_stdev = statistics.stdev(cpu_values)
    threshold = cpu_mean + (2 * cpu_stdev)

    anomalies = []
    for timestamp, value in cpu_history:
        if value > threshold:
            anomalies.append((timestamp, value))

    print(f"\n🚨 CPU Anomalies Detected (>{threshold:.1f}%): {len(anomalies)}")
    for timestamp, value in anomalies[:5]:  # Show first 5
        when = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S.%f')[:-3]
        print(f"   [{when}] {value:.2f}%")

    # ========================================================================
    # SCENARIO 6: Alert Summary
    # ========================================================================
    print("\n\n⚠️  Step 6: Alert summary")
    print("-" * 70)

    if alerts:
        print(f"\n🚨 Total alerts triggered: {len(alerts)}")

        # Count by severity
        warnings = sum(1 for a in alerts if a['severity'] == 'warning')
        criticals = sum(1 for a in alerts if a['severity'] == 'critical')

        print(f"   ⚠️  Warnings: {warnings}")
        print(f"   🚨 Critical: {criticals}")

        # Show recent alerts
        print("\nRecent alerts:")
        for alert in alerts[-5:]:
            time_str = alert['timestamp'].strftime('%H:%M:%S')
            print(f"   [{time_str}] {alert['metric']}: {alert['value']:.2f}")
    else:
        print("✅ No alerts triggered - all metrics within normal range")

    # ========================================================================
    # SCENARIO 7: Time-Series Visualization Data
    # ========================================================================
    print("\n\n📊 Step 7: Preparing data for visualization")
    print("-" * 70)

    # Export CPU usage over time (ready for plotting)
    print("\nCPU usage time series (last 10 samples):")
    print("Time\t\t\tValue\tBar")
    print("-" * 60)

    for timestamp, value in cpu_history[-10:]:
        time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
        bar = '█' * int(value / 5)  # Simple ASCII bar chart
        print(f"{time_str}\t{value:>6.2f}%\t{bar}")

    # ========================================================================
    # SCENARIO 8: Exporting Metrics
    # ========================================================================
    print("\n\n💾 Step 8: Exporting metrics for external analysis")
    print("-" * 70)

    # Export all metrics to JSON
    import json

    metrics_export = {}
    for metric_name in all_metrics:
        history = metrics.history(metric_name)
        metrics_export[metric_name] = [
            {
                'timestamp': datetime.fromtimestamp(ts).isoformat(),
                'value': value
            }
            for ts, value in history
        ]

    with open('/tmp/metrics_export.json', 'w') as f:
        json.dump(metrics_export, f, indent=2)

    print("✅ Metrics exported to /tmp/metrics_export.json")

    # Save ChronoMap with full history
    metrics.save_pickle('/tmp/metrics_history.pkl', compress='lzma')
    print("✅ Full metrics history saved to /tmp/metrics_history.pkl")

    # ========================================================================
    # SCENARIO 9: Pandas Integration (if available)
    # ========================================================================
    print("\n\n📊 Step 9: Pandas DataFrame export (if pandas installed)")
    print("-" * 70)

    try:
        df = metrics.to_dataframe()
        print(f"✅ Created DataFrame with {len(df)} rows")
        print("\nDataFrame preview:")
        print(df.head(10).to_string())

        # Calculate correlation between metrics
        print("\n📈 Metric correlations:")
        pivot = df.pivot_table(
            index='timestamp',
            columns='key',
            values='value'
        )
        correlations = pivot.corr()
        print(correlations.to_string())

    except ImportError:
        print("⚠️  Pandas not installed - skipping DataFrame export")
        print("   Install with: pip install chronomap[pandas]")

    # ========================================================================
    # SCENARIO 10: Performance Statistics
    # ========================================================================
    print("\n\n⚡ Step 10: ChronoMap performance statistics")
    print("-" * 70)

    stats = metrics.get_stats()
    print(f"\nOperation Statistics:")
    print(f"   Total writes: {stats['writes']}")
    print(f"   Total reads: {stats['reads']}")
    print(f"   Cache hit rate: {stats.get('cache_hit_rate', 0):.1f}%")
    print(f"   Auto-prunes: {stats['auto_prunes']}")
    print(f"   Active metrics: {stats['total_keys']}")
    print(f"   Total data points: {stats['total_versions']}")

    # ========================================================================
    # Summary
    # ========================================================================
    print("\n\n" + "=" * 70)
    print("✅ Real-Time Metrics Collection Demo Complete!")
    print("=" * 70)
    print("\n💡 Key Features Demonstrated:")
    print("• Time-series data collection with timestamps")
    print("• Statistical analysis (mean, median, percentiles)")
    print("• Time-range queries (last N seconds/minutes)")
    print("• Real-time alerting with threshold monitoring")
    print("• Anomaly detection using statistical methods")
    print("• Data export for visualization and analysis")
    print("\n🔧 Production Use Cases:")
    print("• Application performance monitoring (APM)")
    print("• IoT sensor data collection")
    print("• Business metrics tracking (KPIs)")
    print("• Server health monitoring")
    print("• API performance monitoring")
    print("\n📝 ChronoMap Advantages:")
    print("• No external dependencies (vs Prometheus, InfluxDB)")
    print("• Built-in statistical analysis")
    print("• Automatic history management (max_history)")
    print("• Perfect for lightweight monitoring")
    print("• Easy integration with existing Python apps")
    print("\n💡 Next Steps:")
    print("• Integrate with Grafana for visualization")
    print("• Add webhook alerts (Slack, PagerDuty)")
    print("• Implement metric retention policies")
    print("• Scale to distributed metrics with event hooks")
    print("=" * 70)


if __name__ == '__main__':
    main()
