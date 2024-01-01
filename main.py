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
from typing import Generator, List, Dict, Optional

from wsgiref.simple_server import make_server, WSGIServer
from prometheus_client.core import (
    REGISTRY, GaugeMetricFamily, InfoMetricFamily, StateSetMetricFamily, Metric
)
from prometheus_client.exposition import make_wsgi_app, _SilentHandler
from prometheus_client.samples import Sample
from pyzm.api import ZMApi
from pyzm.helpers import Monitor, State
from requests import Response

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


def camel_to_snake(name):
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


class ZmExporter:

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
        self._api: ZMApi = ZMApi(options={'apiurl': self._api_url})
        logger.debug('Connected to ZM')
        self.query_time: float = 0.0
        self._monitor_ids: List[int] = []

    def collect(self) -> Generator[Metric, None, None]:
        logger.debug('Beginning collection')
        qstart = time.time()
        for meth in [
            self._do_monitors,
            self._do_states,
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
        """
        - my previous monitoring stuff - https://github.com/jantman/privatepuppet/blob/master/files/simple_monitoring/simple_monitoring.py#L614-L845

        $ curl -s http://bigserver.jasonantman.com/api/monitors/daemonStatus/id:1/daemon:zmc.json | python -mjson.tool
        {
            "status": true,
            "statustext": "'zmc -m 1' running since 23/12/25 15:40:42, pid = 75"
        }

        Inside the container:
        root@c96751634601:/# zmu -lv
          Id Func State TrgState    LastImgTim RdIdx WrIdx LastEvt FrmRate
           1    3     1        0 1703630080.91930237     3     671    9.99
           2    2     1        0 1703630080.92930605     3       0    9.97
           3    3     1        0 1703630080.91930414     0     678    9.97
           4    2     1        0 1703630080.94929610     1       0    9.97
           5    2     1        0 1703630080.952331059     0       0   25.01
        root@c96751634601:/# zmdc.pl check
        running
        root@c96751634601:/# zmdc.pl status
        'zmcontrol.pl --id 4' running since 23/12/25 15:40:43, pid = 99, valid
        'zmeventnotification.pl' running since 23/12/25 15:40:44, pid = 124, valid
        'zmwatch.pl' running since 23/12/25 15:40:44, pid = 115, valid
        'zmc -m 4' running since 23/12/25 15:40:43, pid = 94, valid
        'zmtelemetry.pl' running since 23/12/25 15:40:44, pid = 120, valid
        'zmfilter.pl --filter_id=2 --daemon' running since 23/12/25 15:40:44, pid = 111, valid
        'zmfilter.pl --filter_id=1 --daemon' running since 23/12/25 15:40:43, pid = 107, valid
        'zmcontrol.pl --id 2' running since 23/12/25 15:40:42, pid = 83, valid
        'zmstats.pl' running since 23/12/25 15:40:44, pid = 128, valid
        'zmc -m 2' running since 23/12/25 15:40:42, pid = 79, valid
        'zmcontrol.pl --id 3' running since 23/12/25 15:40:43, pid = 91, valid
        'zmc -m 1' running since 23/12/25 15:40:42, pid = 75, valid
        'zmc -m 5' running since 23/12/25 15:40:43, pid = 103, valid
        'zmc -m 3' running since 23/12/25 15:40:42, pid = 87, valid
        """
        self.query_time = time.time() - qstart
        yield GaugeMetricFamily(
            'zm_query_time_seconds',
            'Time taken to collect data from ZM',
            value=self.query_time
        )
        logger.debug('Finished collection')

    def _do_monitors(self) -> Generator[Metric, None, None]:
        """
        @TODO
        - .status() for each monitor (apparently free-form string?) - being logged as debug
        {'statustext': "'zmc -m 6' running since 23/12/31 16:08:19, pid = 107"}
        """
        logger.debug('Querying monitors')
        monitors: List[Monitor] = self._api.monitors(
            options={'force_reload': True}
        ).list()
        logger.debug('Monitors: %s', [x.get() for x in monitors])
        info = InfoMetricFamily(
            'zm_monitor_info', 'Information about a monitor',
        )
        status = LabeledGaugeMetricFamily(
            'zm_monitor_status','Monitor status'
        )
        event_count = LabeledGaugeMetricFamily(
            'zm_monitor_event_count',
            'Monitor event count'
        )
        event_disk_space = LabeledGaugeMetricFamily(
            'zm_monitor_event_disk_space',
            'Monitor event disk space'
        )
        archived_event_count = LabeledGaugeMetricFamily(
            'zm_monitor_archived_event_count',
            'Monitor archived event count'
        )
        archived_event_disk_space = LabeledGaugeMetricFamily(
            'zm_monitor_archived_event_disk_space',
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
            'zm_monitor_capture_bandwidth',
            'Monitor capture bandwidth'
        )
        self._monitor_ids = []
        m: Monitor
        for m in monitors:
            labels: Dict[str, str] = {
                'id': m.get()['Id'],
                'name': m.get()['Name']
            }
            self._monitor_ids.append(int(m.get()['Id']))
            info.add_metric(labels=labels, value={
                camel_to_snake(x): m.get()[x] for x in [
                    'ServerId', 'StorageId', 'Type', 'DecodingEnabled',
                    'Device', 'Channel', 'Format', 'Method', 'Encoder',
                    'RecordAudio', 'EventPrefix', 'Controllable', 'ControlId',
                    'Importance'
                ]
            })
            status.add_metric(
                labels=labels,
                value=1 if m.status()['status'] else 0
            )
            enabled.add_metric(
                labels=labels, value=1 if m.enabled() else 0
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
            for x in int_fields:
                int_metrics[x].add_metric(
                    labels=labels,
                    value=m.get()[x]
                )
            if m.monitor['Monitor_Status']['Status'] != 'Connected':
                logger.warning(
                    'Monitor %s Status is %s',
                    m.name(), m.monitor['Monitor_Status']['Status']
                )
            connected.add_metric(
                labels=labels,
                value=1 if m.monitor['Monitor_Status']['Status'] == 'Connected'
                else 0
            )
            capture_fps.add_metric(
                labels=labels,
                value=float(m.monitor['Monitor_Status']['CaptureFPS'])
            )
            analysis_fps.add_metric(
                labels=labels,
                value=float(m.monitor['Monitor_Status']['AnalysisFPS'])
            )
            capture_bw.add_metric(
                labels=labels,
                value=float(m.monitor['Monitor_Status']['CaptureBandwidth'])
            )
            event_count.add_metric(
                labels=labels, value=m.monitor['Event_Summary']['TotalEvents']
            )
            event_disk_space.add_metric(
                labels=labels,
                value=m.monitor['Event_Summary']['TotalEventDiskSpace']
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
            info, event_count, enabled, function, connected, capture_fps,
            analysis_fps, capture_bw, event_count, event_disk_space,
            archived_event_count, archived_event_disk_space
        ]
        yield from int_metrics.values()

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
                    'id': s.id(),
                    'definition': s.definition()
                },
                value=1 if s.active() else 0
            )
        yield metric


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
