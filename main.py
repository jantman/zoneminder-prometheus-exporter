#!/usr/bin/env python
"""
https://github.com/jantman/zoneminder-prometheus-exporter

MIT License

Copyright (c) 2024 Jason Antman

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import sys
import os
import argparse
import logging
import socket
import time
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Generator, List, Dict, Optional, Tuple, Any
import json

from wsgiref.simple_server import make_server, WSGIServer
from prometheus_client.core import (
    REGISTRY, GaugeMetricFamily, InfoMetricFamily, StateSetMetricFamily, Metric
)
from prometheus_client.exposition import make_wsgi_app, _SilentHandler
from prometheus_client.samples import Sample
from pyzm.api import ZMApi
from pyzm.ZMMemory import ZMMemory
from pyzm.helpers import Monitor, State
from websocket import create_connection

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


def camel_to_snake(name):
    if name == 'SaveJPEGs':
        return 'save_jpegs'
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def enum_metric_family(
    name: str, documentation: str, states: List[str], value: str
):
    """Since the client library doesn't have this..."""
    if value not in states:
        logger.error(
            'Value of "%s" not listed in states %s for enum_metric_family %s',
            value, states, name
        )
        states.append(value)
    return StateSetMetricFamily(
        name, documentation,
        {
            x: x == value for x in states
        }
    )


class LabeledGaugeMetricFamily(Metric):
    """Not sure why the upstream one doesn't allow labels..."""

    def __init__(
        self,
        name: str,
        documentation: str,
        value: Optional[float] = None,
        labels: Dict[str, str] = None,
        unit: str = '',
    ):
        Metric.__init__(self, name, documentation, 'gauge', unit)
        if labels is None:
            labels = {}
        self._labels = labels
        if value is not None:
            self.add_metric(labels, value)

    def add_metric(self, labels: Dict[str, str], value: float) -> None:
        """Add a metric to the metric family.
        Args:
          labels: A dictionary of labels
          value: A float
        """
        self.samples.append(
            Sample(self.name, dict(labels | self._labels), value, None)
        )


class LabeledStateSetMetricFamily(Metric):
    """Not sure why upstream doesn't allow this..."""

    def __init__(
        self,
        name: str,
        documentation: str,
        labels: Optional[Dict[str, str]] = None,
    ):
        Metric.__init__(self, name, documentation, 'stateset')
        if labels is None:
            labels = {}
        self._labels = labels

    def add_metric(
        self, value: Dict[str, bool], labels: Optional[Dict[str, str]] = None
    ) -> None:
        if labels is None:
            labels = {}
        for state, enabled in sorted(value.items()):
            v = (1 if enabled else 0)
            self.samples.append(Sample(
                self.name,
                dict(self._labels | labels | {self.name: state}),
                v,
            ))


class InvalidStatusStringException(Exception):
    pass


StatusType = Tuple[str, float, int]


def _parse_zm_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse a ZoneMinder events-API datetime string ('YYYY-MM-DD HH:MM:SS')
    into a UTC-aware ``datetime``, or ``None`` if unset/unparseable.

    The ZoneMinder API serializes event StartDateTime/EndDateTime in **UTC**,
    regardless of the server's local timezone. We therefore attach UTC tzinfo
    and callers must compare against ``datetime.now(timezone.utc)`` -- comparing
    against a naive local ``datetime.now()`` would be wrong by the local UTC
    offset (e.g. events appearing hours in the future). Note this differs from
    :meth:`ZmExporter._parse_zmdc_status`, whose daemon-status strings are in
    local time.
    """
    if not value:
        return None
    try:
        return datetime.strptime(
            value, '%Y-%m-%d %H:%M:%S'
        ).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _event_int(raw: Dict[str, Any], key: str) -> int:
    """Return ``raw[key]`` as an int, treating None/''/unparseable as 0.

    ZM's JSON returns numeric fields (DiskSpace, Frames, Emptied) as strings,
    and DiskSpace is None/'' for events whose size ZM has not computed yet.
    """
    val = raw.get(key)
    if val in (None, ''):
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def aggregate_events(
    raw_events: List[Dict[str, Any]],
    monitor_ids: List[int],
    now: datetime,
    window_seconds: int,
    grace_seconds: int,
) -> Dict[int, Dict[str, Any]]:
    """Aggregate raw ZM event dicts (``Event.get()`` output) into per-monitor
    recording-persistence facts. Pure function -- no I/O -- so it is unit
    testable without a live ZoneMinder.

    For each monitor this computes:

    * ``last_event`` -- the newest *ended* event ``(id, end_dt, disk, frames)``,
      used as a freshness gate (a monitor that has not produced a completed
      event recently simply has no ``last_event``).
    * windowed aggregates over events that ended between ``grace_seconds`` and
      ``window_seconds`` ago, excluding still-open events (no ``EndDateTime``)
      and purged events (``Emptied=1``, whose files are legitimately gone):
      ``ended_count``, ``zero_size_count``, ``disk_space_sum``,
      ``min_disk_space``, ``min_frames``.

    Windowed counters default to 0 for every id in ``monitor_ids`` so callers
    can emit a series for every monitor even when it had no recent events.
    """
    def _blank() -> Dict[str, Any]:
        return {
            'ended_count': 0,
            'zero_size_count': 0,
            'disk_space_sum': 0,
            'min_disk_space': None,
            'min_frames': None,
            'last_event': None,
        }

    agg: Dict[int, Dict[str, Any]] = {mid: _blank() for mid in monitor_ids}

    for raw in raw_events:
        try:
            mid = int(raw['MonitorId'])
            eid = int(raw['Id'])
        except (KeyError, ValueError, TypeError):
            continue
        end_dt = _parse_zm_datetime(raw.get('EndDateTime'))
        if end_dt is None:
            # still-open / in-progress event: no final size yet -> ignore
            continue
        m = agg.setdefault(mid, _blank())
        disk = _event_int(raw, 'DiskSpace')
        frames = _event_int(raw, 'Frames')
        # newest ended event by id, regardless of window -> freshness gate
        prev = m['last_event']
        if prev is None or eid > prev[0]:
            m['last_event'] = (eid, end_dt, disk, frames)
        # windowed aggregates: ended in [grace, window] ago, not purged
        end_age = (now - end_dt).total_seconds()
        if not (grace_seconds <= end_age <= window_seconds):
            continue
        if _event_int(raw, 'Emptied') == 1:
            continue
        m['ended_count'] += 1
        m['disk_space_sum'] += disk
        if disk == 0:
            m['zero_size_count'] += 1
        if m['min_disk_space'] is None or disk < m['min_disk_space']:
            m['min_disk_space'] = disk
        if m['min_frames'] is None or frames < m['min_frames']:
            m['min_frames'] = frames
    return agg


class ZmExporter:

    STATUS_RE: re.Pattern = re.compile(
        r"^'(?P<command>[^']+)' running since (?P<year>\d{1,2})/"
        r"(?P<month>\d{1,2})/(?P<day>\d{1,2}) (?P<hour>\d{1,2}):"
        r"(?P<minute>\d{1,2}):(?P<second>\d{1,2}), pid = (?P<pid>\d+).*"
    )

    def _env_or_err(self, name: str) -> str:
        s: str = os.environ.get(name)
        if not s:
            raise RuntimeError(
                f'ERROR: You must set the "{name}" environment variable.'
            )
        return s

    def __init__(self):
        logger.debug('Instantiating ZmExporter')
        self._api_url: str = self._env_or_err('ZM_API_URL')
        logger.info('Connecting to ZM API at: %s', self._api_url)
        
        # Build options dict and add optional authentication credentials if provided
        api_options: Dict[str, Any] = {'apiurl': self._api_url}
        zm_user: Optional[str] = os.environ.get('ZM_USER')
        zm_password: Optional[str] = os.environ.get('ZM_PASSWORD')
        
        if zm_user and zm_password:
            logger.debug('Using ZoneMinder authentication')
            api_options['user'] = zm_user
            api_options['password'] = zm_password
        elif zm_user or zm_password:
            logger.warning(
                'Both ZM_USER and ZM_PASSWORD must be provided for authentication. '
                'Only one was provided; proceeding without authentication.'
            )
        
        self._api: ZMApi = ZMApi(options=api_options)
        logger.debug('Connected to ZM')
        self.query_time: float = 0.0
        self._monitor_id_to_name: Dict[int, str] = {}
        # Recording-persistence event metrics: aggregate over events that ended
        # in the last ZM_EVENT_WINDOW_SECONDS (default 15m), ignoring the most
        # recent ZM_EVENT_GRACE_SECONDS (default 2m) so events whose DiskSpace
        # ZM has not finished computing yet do not read as zero-size failures.
        # ZM_EVENT_QUERY_LIMIT bounds how many events a single scrape fetches;
        # keep it comfortably above the busiest window so results are not
        # truncated (pyzm sorts newest-first and stops at the limit).
        self._event_window_seconds: int = int(
            os.environ.get('ZM_EVENT_WINDOW_SECONDS', '900')
        )
        self._event_grace_seconds: int = int(
            os.environ.get('ZM_EVENT_GRACE_SECONDS', '120')
        )
        self._event_query_limit: int = int(
            os.environ.get('ZM_EVENT_QUERY_LIMIT', '500')
        )
        # ZoneMinder's events API filters by StartTime in the ZM SERVER's local
        # timezone (while returning EndDateTime in UTC -- yes, inconsistent). We
        # compute the events query's `from` bound in an explicit timezone so it
        # is correct regardless of THIS process's timezone -- the exporter
        # container often runs as UTC even when ZM does not, which would push
        # the bound into the future and return zero events. Source the tz from
        # ZM_EVENT_QUERY_TZ, then TZ; if neither resolves, fall back to a
        # process-local relative bound (correct only when this process's tz
        # already matches the ZM server's).
        self._event_query_tz: Optional[ZoneInfo] = None
        tz_name: Optional[str] = (
            os.environ.get('ZM_EVENT_QUERY_TZ') or os.environ.get('TZ')
        )
        if tz_name:
            try:
                self._event_query_tz = ZoneInfo(tz_name)
            except (ZoneInfoNotFoundError, ValueError) as ex:
                logger.warning(
                    'Could not resolve timezone %r for event queries (%s); '
                    'falling back to process-local time. Ensure the tzdata '
                    'package is installed or set a valid ZM_EVENT_QUERY_TZ.',
                    tz_name, ex
                )

    def collect(self) -> Generator[Metric, None, None]:
        logger.debug('Beginning collection')
        qstart = time.time()
        for meth in [
            self._do_monitors,
            self._do_events,
            self._do_states,
            self._do_monitor_shm,
            self._do_zmes_websocket,
        ]:
            yield from meth()
        dc_url: str = self._api.api_url + '/host/daemonCheck.json'
        logger.debug('GET %s', dc_url)
        dc_resp: dict = self._api._make_request(url=dc_url)
        logger.debug(
            '%s responded with: %s',dc_url, dc_resp
        )
        yield GaugeMetricFamily(
            name='zm_daemon_check', documentation='ZM daemon check',
            value=dc_resp['result']
        )
        self.query_time = time.time() - qstart
        yield GaugeMetricFamily(
            'zm_query_time_seconds',
            'Time taken to collect data from ZM',
            value=self.query_time
        )
        logger.debug('Finished collection')

    def _parse_zmdc_status(self, status: str) -> StatusType:
        m: Optional[re.Match]
        if not (m := self.STATUS_RE.match(status)):
            raise InvalidStatusStringException(
                f'Not a parseable status: {status}'
            )
        dt: datetime = datetime(
            year=int(f'20{m.group("year")}'),
            month=int(m.group('month')), day=int(m.group('day')),
            hour=int(m.group('hour')), minute=int(m.group('minute')),
            second=int(m.group('second'))
        )
        now: datetime = datetime.now()
        age: float = (now - dt).total_seconds()
        return m.group('command'), age, int(m.group('pid'))

    def _do_monitors(self) -> Generator[Metric, None, None]:
        logger.debug('Querying monitors')
        monitors: List[Monitor] = self._api.monitors(
            options={'force_reload': True}
        ).list()
        logger.debug('Monitors: %s', [x.get() for x in monitors])
        info = InfoMetricFamily(
            'zm_monitor', 'Information about a monitor',
        )
        zmc = LabeledGaugeMetricFamily(
            'zm_monitor_zmc_uptime_seconds',
            'Uptime of monitor zmc process in seconds'
        )
        zmc_pid = LabeledGaugeMetricFamily(
            'zm_monitor_zmc_pid',
            'Monitor zmc process PID'
        )
        status = LabeledGaugeMetricFamily(
            'zm_monitor_status', 'Monitor status'
        )
        event_count = LabeledGaugeMetricFamily(
            'zm_monitor_event_count',
            'Monitor event count'
        )
        event_disk_space = LabeledGaugeMetricFamily(
            'zm_monitor_event_disk_space_bytes',
            'Monitor event disk space'
        )
        archived_event_count = LabeledGaugeMetricFamily(
            'zm_monitor_archived_event_count',
            'Monitor archived event count'
        )
        archived_event_disk_space = LabeledGaugeMetricFamily(
            'zm_monitor_archived_event_disk_space_bytes',
            'Monitor archived event disk space'
        )
        enabled = LabeledGaugeMetricFamily(
            'zm_monitor_enabled',
            'Monitor is enabled'
        )
        function = LabeledStateSetMetricFamily(
            'zm_monitor_function',
            'Monitor function'
        )
        capturing = LabeledStateSetMetricFamily(
            'zm_monitor_capturing',
            'Monitor capturing mode'
        )
        analysing = LabeledStateSetMetricFamily(
            'zm_monitor_analysing',
            'Monitor analysing mode'
        )
        recording = LabeledStateSetMetricFamily(
            'zm_monitor_recording',
            'Monitor recording mode'
        )
        decoding = LabeledStateSetMetricFamily(
            'zm_monitor_decoding',
            'Monitor decoding mode'
        )
        janus_enabled = LabeledGaugeMetricFamily(
            'zm_monitor_janus_enabled',
            'Monitor Janus streaming enabled'
        )
        go2rtc_enabled = LabeledGaugeMetricFamily(
            'zm_monitor_go2rtc_enabled',
            'Monitor Go2RTC streaming enabled'
        )
        rtsp2web_enabled = LabeledGaugeMetricFamily(
            'zm_monitor_rtsp2web_enabled',
            'Monitor RTSP2Web streaming enabled'
        )
        mqtt_enabled = LabeledGaugeMetricFamily(
            'zm_monitor_mqtt_enabled',
            'Monitor MQTT enabled'
        )
        onvif_event_listener = LabeledGaugeMetricFamily(
            'zm_monitor_onvif_event_listener',
            'Monitor ONVIF event listener enabled'
        )
        int_fields: List[str] = [
            'DecodingEnabled', 'Width', 'Height', 'Colours', 'Palette',
            'SaveJPEGs', 'VideoWriter', 'OutputCodec', 'Brightness', 'Contrast',
            'Hue', 'Colour', 'ImageBufferCount', 'MaxImageBufferCount',
            'WarmupCount', 'PreEventCount', 'PostEventCount', 'AlarmFrameCount',
            'RefBlendPerc', 'AlarmRefBlendPerc', 'TrackMotion', 'ZoneCount',
        ]
        int_metrics: Dict[str, LabeledGaugeMetricFamily] = {
            x: LabeledGaugeMetricFamily(
                f'zm_monitor_{camel_to_snake(x)}',
                f'ZM Monitor {x}'
            ) for x in int_fields
        }
        connected = LabeledGaugeMetricFamily(
            'zm_monitor_connected',
            'Monitor is connected or not'
        )
        capture_fps = LabeledGaugeMetricFamily(
            'zm_monitor_capture_fps',
            'Monitor capture FPS'
        )
        analysis_fps = LabeledGaugeMetricFamily(
            'zm_monitor_analysis_fps',
            'Monitor analysis FPS'
        )
        capture_bw = LabeledGaugeMetricFamily(
            'zm_monitor_capture_bandwidth_bytes_per_second',
            'Monitor capture bandwidth'
        )
        self._monitor_id_to_name: Dict[int, str] = {}
        m: Monitor
        for m in monitors:
            # ZoneMinder soft-deletes monitors: a deleted monitor is flagged
            # Deleted=true and keeps being returned by the API (with all-null
            # Monitor_Status) until a later cleanup pass removes the row. Skip
            # these entirely so we don't emit stale metrics or choke on nulls.
            if m.get().get('Deleted'):
                logger.debug(
                    'Skipping deleted monitor %s (%s)',
                    m.get()['Id'], m.get()['Name']
                )
                continue
            labels: Dict[str, str] = {
                'id': str(m.get()['Id']),
                'name': m.get()['Name']
            }
            self._monitor_id_to_name[int(m.get()['Id'])] = m.get()['Name']
            info_vals: dict = {
                camel_to_snake(x): str(m.get()[x]) for x in [
                    'ServerId', 'StorageId', 'Type', 'DecodingEnabled',
                    'Device', 'Channel', 'Format', 'Method', 'Encoder',
                    'RecordAudio', 'EventPrefix', 'Controllable', 'ControlId',
                    'Importance'
                ]
            } | {
                camel_to_snake(x): str(m.get().get(x, ''))
                for x in [
                    'Capturing', 'Analysing', 'Recording',
                    'Decoding', 'OutputCodecName'
                ]
            } | labels
            info.add_metric(labels=list(info_vals.keys()), value=info_vals)
            curr_status = m.status()
            status.add_metric(
                labels=labels,
                value=1 if curr_status['status'] else 0
            )
            statustext: str = curr_status['statustext'] or ''
            # Skip parsing for expected non-running states: a monitor with
            # capturing disabled, or one whose daemon isn't running (e.g. a
            # monitor that was just deleted but still appears in the API).
            if (
                statustext not in (
                    'Monitor function is set to None',
                    'Monitor capturing is set to None',
                )
                and not statustext.endswith('not running')
            ):
                try:
                    foo: StatusType = self._parse_zmdc_status(statustext)
                    zmc.add_metric(
                        labels=labels | {'command': foo[0]}, value=foo[1]
                    )
                    zmc_pid.add_metric(
                        labels=labels | {'command': foo[0]}, value=foo[2]
                    )
                except Exception as ex:
                    logger.error(
                        'Error parsing monitor %s status string "%s": %s',
                        labels, statustext, ex,
                        exc_info=True
                    )
            # In ZM 1.38+, Enabled is always 0 and Capturing replaces it.
            # Use Capturing != 'None' as the enabled indicator when available.
            if m.get().get('Capturing') is not None:
                enabled.add_metric(
                    labels=labels,
                    value=0 if m.get()['Capturing'] == 'None' else 1
                )
            else:
                enabled.add_metric(
                    labels=labels, value=int(m.get()['Enabled'])
                )
            function.add_metric(
                value={
                    x: m.function() == x
                    for x in [
                        'None', 'Monitor', 'Modect', 'Record', 'Mocord',
                        'Nodect'
                    ]
                },
                labels=labels
            )
            cap_val = m.get().get('Capturing', 'Unknown')
            capturing.add_metric(
                value={
                    x: cap_val == x
                    for x in ['None', 'Ondemand', 'Always']
                },
                labels=labels
            )
            ana_val = m.get().get('Analysing', 'Unknown')
            analysing.add_metric(
                value={
                    x: ana_val == x
                    for x in ['None', 'Always']
                },
                labels=labels
            )
            rec_val = m.get().get('Recording', 'Unknown')
            recording.add_metric(
                value={
                    x: rec_val == x
                    for x in ['None', 'OnMotion', 'Always']
                },
                labels=labels
            )
            dec_val = m.get().get('Decoding', 'Unknown')
            decoding.add_metric(
                value={
                    x: dec_val == x
                    for x in [
                        'None', 'Ondemand', 'KeyFrames',
                        'KeyFrames+Ondemand', 'Always'
                    ]
                },
                labels=labels
            )
            janus_enabled.add_metric(
                labels=labels,
                value=int(m.get().get('JanusEnabled', '0'))
            )
            go2rtc_enabled.add_metric(
                labels=labels,
                value=int(m.get().get('Go2RTCEnabled', '0'))
            )
            rtsp2web_enabled.add_metric(
                labels=labels,
                value=int(m.get().get('RTSP2WebEnabled', '0'))
            )
            mqtt_enabled.add_metric(
                labels=labels,
                value=int(m.get().get('MQTT_Enabled', '0'))
            )
            onvif_event_listener.add_metric(
                labels=labels,
                value=int(m.get().get('ONVIF_Event_Listener', '0'))
            )
            for x in int_fields:
                int_metrics[x].add_metric(
                    labels=labels,
                    value=0 if m.get()[x] is None else int(m.get()[x])
                )
            # Monitor_Status (and its fields) can be None when a monitor's
            # capture daemon isn't running, e.g. a monitor that was just
            # deleted but still appears in the API for one scrape.
            mon_status: dict = m.monitor.get('Monitor_Status') or {}
            status_str: str = mon_status.get('Status') or 'Unknown'
            if status_str != 'Connected':
                logger.warning(
                    'Monitor %s Status is %s', m.name(), status_str
                )
            connected.add_metric(
                labels=labels | {'status': status_str},
                value=1 if status_str == 'Connected' else 0
            )
            capture_fps.add_metric(
                labels=labels,
                value=float(mon_status.get('CaptureFPS') or 0)
            )
            analysis_fps.add_metric(
                labels=labels,
                value=float(mon_status.get('AnalysisFPS') or 0)
            )
            capture_bw.add_metric(
                labels=labels,
                value=float(mon_status.get('CaptureBandwidth') or 0)
            )
            event_count.add_metric(
                labels=labels,
                value=0 if m.monitor['Event_Summary']['TotalEvents'] is None
                else m.monitor['Event_Summary']['TotalEvents']
            )
            event_disk_space.add_metric(
                labels=labels,
                value=0 if m.monitor['Event_Summary']['TotalEventDiskSpace'] is None
                else m.monitor['Event_Summary']['TotalEventDiskSpace']
            )
            archived_event_count.add_metric(
                labels=labels,
                value=0 if not m.monitor['Event_Summary']['ArchivedEvents']
                else m.monitor['Event_Summary']['ArchivedEvents']
            )
            archived_event_disk_space.add_metric(
                labels=labels,
                value=0 if not m.monitor['Event_Summary']['ArchivedEventDiskSpace']
                else m.monitor['Event_Summary']['ArchivedEventDiskSpace']
            )
        yield from [
            info, event_count, enabled, function,
            capturing, analysing, recording, decoding,
            janus_enabled, go2rtc_enabled, rtsp2web_enabled,
            mqtt_enabled, onvif_event_listener,
            connected, capture_fps,
            analysis_fps, capture_bw, event_disk_space,
            archived_event_count, archived_event_disk_space, zmc, zmc_pid
        ]
        yield from int_metrics.values()

    def _do_events(self) -> Generator[Metric, None, None]:
        """Recording-persistence metrics derived from recently-ended events.

        Every existing monitor metric proves *capture* is alive; these prove
        events actually reached *disk*. Queries events over a window slightly
        wider than ``ZM_EVENT_WINDOW_SECONDS`` (ZM filters by start time, so we
        pad to still catch long events that ended inside the window), then
        aggregates per monitor via :func:`aggregate_events`.
        """
        window: int = self._event_window_seconds
        grace: int = self._event_grace_seconds
        # Fetch events whose StartTime is within the window plus a 15-minute
        # pad (ZM filters by StartTime; the pad covers long events that ended
        # inside the window). Compute the bound in the ZM server timezone when
        # known so it is correct even if this process runs as UTC; otherwise
        # fall back to a process-local relative bound.
        pad_seconds: int = window + 15 * 60
        if self._event_query_tz is not None:
            from_bound: str = (
                datetime.now(self._event_query_tz)
                - timedelta(seconds=pad_seconds)
            ).strftime('%Y-%m-%d %H:%M:%S')
        else:
            from_bound = f'{pad_seconds // 60} minutes ago'
        options: Dict[str, Any] = {
            'from': from_bound,
            'limit': self._event_query_limit,
        }
        logger.debug('Querying events with options: %s', options)
        try:
            raw_events: List[Dict[str, Any]] = [
                e.get() for e in self._api.events(options=options).list()
            ]
        except Exception as ex:
            logger.error('Error querying events: %s', ex, exc_info=True)
            return
        logger.debug('Fetched %d events for window', len(raw_events))
        # ZM's events API returns event datetimes in UTC (see
        # _parse_zm_datetime), so compare against a UTC-aware now.
        now: datetime = datetime.now(timezone.utc)
        agg: Dict[int, Dict[str, Any]] = aggregate_events(
            raw_events, list(self._monitor_id_to_name.keys()),
            now, window, grace
        )

        last_disk = LabeledGaugeMetricFamily(
            'zm_monitor_last_event_disk_space_bytes',
            'DiskSpace in bytes of the most recent ended event for this monitor'
        )
        last_age = LabeledGaugeMetricFamily(
            'zm_monitor_last_event_end_time_age_seconds',
            'Seconds since the most recent ended event for this monitor ended'
        )
        last_frames = LabeledGaugeMetricFamily(
            'zm_monitor_last_event_frames',
            'Frame count of the most recent ended event for this monitor'
        )
        last_id = LabeledGaugeMetricFamily(
            'zm_monitor_last_event_id',
            'Event ID of the most recent ended event for this monitor '
            '(monotonic; safe to use with increase() as an event-creation rate)'
        )
        ended_count = LabeledGaugeMetricFamily(
            'zm_monitor_recent_ended_event_count',
            f'Count of events that ended in the last {window}s (excludes '
            f'still-open and purged events; windowed gauge, do not rate())'
        )
        zero_count = LabeledGaugeMetricFamily(
            'zm_monitor_recent_ended_zero_size_event_count',
            f'Count of events that ended in the last {window}s having saved '
            f'zero bytes to disk (windowed gauge, do not rate())'
        )
        disk_sum = LabeledGaugeMetricFamily(
            'zm_monitor_recent_event_disk_space_bytes',
            f'Sum of DiskSpace in bytes over events that ended in the last '
            f'{window}s -- recording throughput (windowed gauge, do not rate())'
        )
        min_disk = LabeledGaugeMetricFamily(
            'zm_monitor_recent_min_event_disk_space_bytes',
            f'Smallest DiskSpace in bytes among events that ended in the last '
            f'{window}s -- surfaces partial/truncated writes (windowed gauge)'
        )
        min_frames = LabeledGaugeMetricFamily(
            'zm_monitor_recent_min_event_frames',
            f'Smallest frame count among events that ended in the last '
            f'{window}s -- surfaces truncated events (windowed gauge)'
        )

        for mid, name in sorted(self._monitor_id_to_name.items()):
            m: Optional[Dict[str, Any]] = agg.get(mid)
            if not m:
                continue
            labels: Dict[str, str] = {'id': str(mid), 'name': name}
            # windowed metrics: always emit (0 default) so a series exists for
            # every monitor and "count > 0" alerts have something to evaluate.
            ended_count.add_metric(labels=labels, value=m['ended_count'])
            zero_count.add_metric(labels=labels, value=m['zero_size_count'])
            disk_sum.add_metric(labels=labels, value=m['disk_space_sum'])
            if m['min_disk_space'] is not None:
                min_disk.add_metric(labels=labels, value=m['min_disk_space'])
            if m['min_frames'] is not None:
                min_frames.add_metric(labels=labels, value=m['min_frames'])
            # point metrics: only when there is a recent ended event, so a
            # quiet camera (no events) does not emit a stale/false series.
            if m['last_event'] is not None:
                eid, end_dt, disk, frames = m['last_event']
                last_disk.add_metric(labels=labels, value=disk)
                last_age.add_metric(
                    labels=labels, value=(now - end_dt).total_seconds()
                )
                last_frames.add_metric(labels=labels, value=frames)
                last_id.add_metric(labels=labels, value=eid)
        yield from [
            last_disk, last_age, last_frames, last_id,
            ended_count, zero_count, disk_sum, min_disk, min_frames,
        ]

    def _do_monitor_shm(self) -> Generator[Metric, None, None]:
        int_fields: List[str] = [
            'action', 'audio_channels', 'audio_frequency', 'imagesize',
            'last_event', 'last_frame_score', 'last_read_index',
            'last_write_index', 'state'
        ]
        bool_fields: List[str] = ['active', 'format', 'signal']
        ts_fields: List[str] = [
            'heartbeat_time', 'last_read_time', 'last_write_time',
            'startup_time'
        ]
        metrics: Dict[str, LabeledGaugeMetricFamily] = {}
        for i in int_fields + bool_fields:
            metrics[i] = LabeledGaugeMetricFamily(
                f'zm_monitor_mmap_{i}',
                f'ZM Monitor MMAP field {i}'
            )
        for i in ts_fields:
            metrics[i] = LabeledGaugeMetricFamily(
                f'zm_monitor_mmap_{i}_age_seconds',
                f'Seconds since value of ZM Monitor MMAP field {i}'
            )
        logger.debug('Handling monitor mmaps...')
        mid: int
        mname: str
        for mid, mname in sorted(self._monitor_id_to_name.items()):
            shm_path: str = f'/dev/shm/zm.mmap.{mid}'
            if not os.path.exists(shm_path):
                logger.warning(
                    'mmap file for Monitor %s at %s does not exist; skipping.',
                    mid, shm_path
                )
                continue
            logger.debug('Reading shared memory for monitor %s', mid)
            now: int = int(time.time())
            labels: Dict[str, str] = {'id': str(mid), 'name': mname}
            try:
                mem: ZMMemory = ZMMemory(mid=mid)
                data: dict = mem.get_shared_data()
                mem.close()
            except Exception as ex:
                logger.error(
                    'Error reading shared memory for monitor %s: %s',
                    mid, ex, exc_info=True
                )
                continue
            for i in int_fields:
                metrics[i].add_metric(
                    labels=labels,
                    value=data[i]
                )
            for i in bool_fields:
                metrics[i].add_metric(
                    labels=labels,
                    value=1 if data[i] else 0
                )
            for i in ts_fields:
                metrics[i].add_metric(
                    labels=labels,
                    value=now - data[i]
                )
        yield from metrics.values()

    def _do_states(self) -> Generator[Metric, None, None]:
        logger.debug('Getting ZM states')
        states: List[State] = self._api.states().list()
        metric = LabeledGaugeMetricFamily(
            'zm_state',
            'Monitor state'
        )
        s: State
        for s in states:
            metric.add_metric(
                labels={
                    'name': s.name(),
                    'id': str(s.id()),
                    'definition': str(s.definition())
                },
                value=s.get()['IsActive']
            )
        yield metric

    def _do_zmes_websocket(self) -> Generator[Metric, None, None]:
        wsurl: Optional[str] = os.environ.get('ZMES_WEBSOCKET_URL')
        if not wsurl:
            logger.debug(
                'ZMES_WEBSOCKET_URL not set; not checking websocket server'
            )
            return
        start = time.time()
        try:
            logger.debug('Connecting to websocket server at: %s', wsurl)
            ws = create_connection(wsurl, timeout=10)
            ws.send('{"event":"control","data":{"type":"version"}}')
            val = ws.recv()
            ws.close()
            data = json.loads(val)
            logger.debug('Websocket response: %s', data)
            duration = time.time() - start
            assert data['status'] == 'Success'
            yield LabeledGaugeMetricFamily(
                'zm_zmes_websocket_response_time_seconds',
                'ZMES websocket server response time to '
                'version request, and status response as a label',
                value=duration,
                labels={'status': data['status']}
            )
        except Exception as ex:
            logger.warning(
                'Error connecting to websocket server at %s: %s',
                wsurl, ex, exc_info=True
            )
            duration = time.time() - start
            yield LabeledGaugeMetricFamily(
                'zm_zmes_websocket_response_time_seconds',
                'ZMES websocket server response time to '
                'version request, and status response as a label',
                value=duration,
                labels={'status': 'Exception'}
            )


def _get_best_family(address, port):
    """
    Automatically select address family depending on address
    copied from prometheus_client.exposition.start_http_server
    """
    # HTTPServer defaults to AF_INET, which will not start properly if
    # binding an ipv6 address is requested.
    # This function is based on what upstream python did for http.server
    # in https://github.com/python/cpython/pull/11767
    infos = socket.getaddrinfo(address, port)
    family, _, _, _, sockaddr = next(iter(infos))
    return family, sockaddr[0]


def serve_exporter(port: int, addr: str = '0.0.0.0'):
    """
    Copied from prometheus_client.exposition.start_http_server, but doesn't run
    in a thread because we're just a proxy.
    """

    class TmpServer(WSGIServer):
        """Copy of WSGIServer to update address_family locally"""

    TmpServer.address_family, addr = _get_best_family(addr, port)
    app = make_wsgi_app(REGISTRY)
    httpd = make_server(
        addr, port, app, TmpServer, handler_class=_SilentHandler
    )
    httpd.serve_forever()


def parse_args(argv):
    p = argparse.ArgumentParser(description='ZoneMinder exporter')
    p.add_argument(
        '-v', '--verbose', dest='verbose', action='count', default=0,
        help='verbose output. specify twice for debug-level output.'
    )
    args = p.parse_args(argv)
    return args


def set_log_info():
    set_log_level_format(
        logging.INFO, '%(asctime)s %(levelname)s:%(name)s:%(message)s'
    )


def set_log_debug():
    set_log_level_format(
        logging.DEBUG,
        "%(asctime)s [%(levelname)s %(filename)s:%(lineno)s - "
        "%(name)s.%(funcName)s() ] %(message)s"
    )


def set_log_level_format(level: int, fmt: str):
    """
    Set logger level and format.

    :param level: logging level; see the :py:mod:`logging` constants.
    :type level: int
    :param format: logging formatter format string
    :type format: str
    """
    formatter = logging.Formatter(fmt=fmt)
    logger.handlers[0].setFormatter(formatter)
    logger.setLevel(level)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    if args.verbose > 1:
        set_log_debug()
    elif args.verbose == 1:
        set_log_info()
    logger.debug('Registering collector...')
    REGISTRY.register(ZmExporter())
    logger.info('Starting HTTP server on port %d', 8080)
    serve_exporter(8080)
