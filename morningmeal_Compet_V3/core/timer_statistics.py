"""Read-only totals for the timer distribution view."""
import math


def timer_distribution(timers):
    rows = []
    for index, timer in enumerate(timers):
        try:
            value = float(timer.get('elapsed_seconds', 0))
            seconds = int(value) if math.isfinite(value) and value > 0 else 0
        except (ValueError, TypeError, OverflowError):
            seconds = 0
        rows.append({'id': timer.get('id', str(index)), 'name': timer.get('name', ''), 'seconds': seconds})
    total = sum(row['seconds'] for row in rows)
    for row in rows:
        row['share'] = row['seconds'] / total if total else 0
    return rows, total
