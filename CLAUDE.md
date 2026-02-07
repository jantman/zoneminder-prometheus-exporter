# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Docker-based Prometheus exporter for ZoneMinder. Single-file Python application (`main.py`, ~600 lines) that collects metrics from ZoneMinder's API (via `pyzm` library) and shared memory (`/dev/shm/zm.mmap.*`), exposing them on port 8080 for Prometheus scraping. Personal WIP project, no formal test suite.

## Development Setup

```bash
python3 -mvenv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
./main.py              # WARNING-level logging
./main.py -v           # INFO-level logging
./main.py -vv          # DEBUG-level logging
```

Requires `ZM_API_URL` env var (e.g., `http://zmhost/zm/api`). Optional: `ZMES_WEBSOCKET_URL` for WebSocket connectivity testing.

Must run on the same machine as ZoneMinder (needs shared memory access via `/dev/shm/`).

## Docker Build & Release

Build validates on push to `main` via GitHub Actions. Releases are triggered by git tags, which automatically build and push images to Docker Hub (`jantman/zoneminder-prometheus-exporter`) and GHCR.

```bash
docker build -t zoneminder-prometheus-exporter .
```

## Architecture

All logic lives in `main.py`:

- **`ZmExporter`** class: Core Prometheus collector implementing `collect()`. Connects to ZoneMinder API via `pyzm.api.ZMApi` and reads shared memory via `pyzm.ZMMemory.ZMMemory`.
  - `_do_monitors()`: Collects monitor status, events, FPS, bandwidth, disk space metrics from the ZM API
  - `_do_monitor_shm()`: Reads metrics from ZoneMinder shared memory mmap files
  - `_do_states()`: Collects ZoneMinder state information
  - `_do_zmes_websocket()`: Tests ZMES WebSocket server connectivity
- **`LabeledGaugeMetricFamily`** / **`LabeledStateSetMetricFamily`**: Custom metric family classes extending prometheus_client to support labeled metrics
- **`serve_exporter()`**: WSGI server function using `wsgiref.simple_server`

## Key Dependencies

- `prometheus-client`: Prometheus metrics exposition
- `pyzm`: ZoneMinder Python API (uses author's fork at `github.com/jantman/pyzm` — the upstream library has quirks: custom non-standard logging, incorrect docs, not well maintained)
- `websocket-client`: For ZMES WebSocket connectivity testing

## Important Notes

- No authentication support for ZoneMinder currently
- The `pyzm` dependency is a git-based fork, not a PyPI package
- Metrics are generated on-demand per Prometheus scrape (no persistent state)
- `camel_to_snake()` helper converts ZoneMinder's CamelCase field names to Prometheus-style snake_case metric names
