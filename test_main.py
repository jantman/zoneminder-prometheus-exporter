"""Unit tests for the pure event-aggregation logic in main.aggregate_events.

Run with: python -m unittest test_main
"""

import unittest
from datetime import datetime, timedelta, timezone

from main import aggregate_events, _parse_zm_datetime, _event_int

# ZM's events API returns UTC; the exporter compares against a UTC-aware now.
NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
WINDOW = 900   # 15m
GRACE = 120    # 2m


def _event(eid, mid, *, ended_ago=None, disk='1000', frames='30',
           emptied='0', open_event=False):
    """Build a raw ZM event dict (Event.get() shape). ``ended_ago`` is seconds
    before NOW that the event ended; ``open_event`` leaves EndDateTime null."""
    end = None if open_event else (
        (NOW - timedelta(seconds=ended_ago)).strftime('%Y-%m-%d %H:%M:%S')
    )
    return {
        'Id': str(eid),
        'MonitorId': str(mid),
        'StartDateTime': (NOW - timedelta(seconds=(ended_ago or 0) + 30)
                          ).strftime('%Y-%m-%d %H:%M:%S'),
        'EndDateTime': end,
        'DiskSpace': disk,
        'Frames': frames,
        'Emptied': emptied,
    }


class TestParsingHelpers(unittest.TestCase):

    def test_parse_datetime(self):
        self.assertEqual(
            _parse_zm_datetime('2026-07-12 11:59:00'),
            datetime(2026, 7, 12, 11, 59, 0, tzinfo=timezone.utc),
        )
        self.assertIsNone(_parse_zm_datetime(None))
        self.assertIsNone(_parse_zm_datetime(''))
        self.assertIsNone(_parse_zm_datetime('not-a-date'))

    def test_event_int(self):
        self.assertEqual(_event_int({'DiskSpace': '4096'}, 'DiskSpace'), 4096)
        self.assertEqual(_event_int({'DiskSpace': None}, 'DiskSpace'), 0)
        self.assertEqual(_event_int({'DiskSpace': ''}, 'DiskSpace'), 0)
        self.assertEqual(_event_int({}, 'DiskSpace'), 0)
        self.assertEqual(_event_int({'DiskSpace': 'x'}, 'DiskSpace'), 0)


class TestAggregateEvents(unittest.TestCase):

    def test_no_events_defaults_to_zero_series(self):
        agg = aggregate_events([], [1, 2], NOW, WINDOW, GRACE)
        self.assertEqual(set(agg), {1, 2})
        for mid in (1, 2):
            self.assertEqual(agg[mid]['ended_count'], 0)
            self.assertEqual(agg[mid]['zero_size_count'], 0)
            self.assertEqual(agg[mid]['disk_space_sum'], 0)
            self.assertIsNone(agg[mid]['last_event'])
            self.assertIsNone(agg[mid]['min_disk_space'])

    def test_healthy_events(self):
        events = [
            _event(10, 1, ended_ago=300, disk='2000', frames='40'),
            _event(11, 1, ended_ago=200, disk='3000', frames='50'),
        ]
        agg = aggregate_events(events, [1], NOW, WINDOW, GRACE)
        m = agg[1]
        self.assertEqual(m['ended_count'], 2)
        self.assertEqual(m['zero_size_count'], 0)
        self.assertEqual(m['disk_space_sum'], 5000)
        self.assertEqual(m['min_disk_space'], 2000)
        self.assertEqual(m['min_frames'], 40)
        # newest by id is 11
        self.assertEqual(m['last_event'][0], 11)
        self.assertEqual(m['last_event'][2], 3000)

    def test_zero_size_event_counted(self):
        events = [
            _event(20, 1, ended_ago=300, disk='2000'),
            _event(21, 1, ended_ago=250, disk='0'),      # failed write
            _event(22, 1, ended_ago=240, disk=None),     # DiskSpace not set
        ]
        m = aggregate_events(events, [1], NOW, WINDOW, GRACE)[1]
        self.assertEqual(m['ended_count'], 3)
        self.assertEqual(m['zero_size_count'], 2)
        self.assertEqual(m['min_disk_space'], 0)

    def test_grace_excludes_freshly_ended(self):
        # ended 60s ago (< grace 120s): DiskSpace may not be computed yet, so
        # it must NOT be counted (would be a false zero-size positive).
        events = [_event(30, 1, ended_ago=60, disk='0')]
        m = aggregate_events(events, [1], NOW, WINDOW, GRACE)[1]
        self.assertEqual(m['ended_count'], 0)
        self.assertEqual(m['zero_size_count'], 0)
        # still visible as the newest ended event (freshness gate)
        self.assertEqual(m['last_event'][0], 30)

    def test_window_excludes_old_events(self):
        events = [_event(40, 1, ended_ago=WINDOW + 300, disk='0')]
        m = aggregate_events(events, [1], NOW, WINDOW, GRACE)[1]
        self.assertEqual(m['ended_count'], 0)
        self.assertEqual(m['zero_size_count'], 0)

    def test_purged_event_not_a_failure(self):
        # Emptied=1: files legitimately purged, must not count as zero-size.
        events = [_event(50, 1, ended_ago=300, disk='0', emptied='1')]
        m = aggregate_events(events, [1], NOW, WINDOW, GRACE)[1]
        self.assertEqual(m['ended_count'], 0)
        self.assertEqual(m['zero_size_count'], 0)

    def test_open_event_ignored(self):
        events = [
            _event(60, 1, open_event=True),                 # recording now
            _event(61, 1, ended_ago=300, disk='1500'),
        ]
        m = aggregate_events(events, [1], NOW, WINDOW, GRACE)[1]
        self.assertEqual(m['ended_count'], 1)
        # newest *ended* event is 61, not the open 60
        self.assertEqual(m['last_event'][0], 61)

    def test_unknown_monitor_gets_entry(self):
        # event for a monitor not in the provided id list still aggregates
        events = [_event(70, 9, ended_ago=300, disk='0')]
        agg = aggregate_events(events, [1], NOW, WINDOW, GRACE)
        self.assertIn(9, agg)
        self.assertEqual(agg[9]['zero_size_count'], 1)


if __name__ == '__main__':
    unittest.main()
