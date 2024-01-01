# zoneminder-prometheus-exporter

A docker-based Prometheus exporter for ZoneMinder.

[![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)

**IMPORTANT:** This is a personal project only. PRs are accepted, but this is not supported and "issues" will likely not be fixed or responded to. This is only for people who understand the details of everything invovled.

## Usage

This is really only intended to be run in Docker; if you need to run it locally, make your environment like the Docker container.

If you are also running ZoneMinder itself inside Docker, i.e. with [my docker-zoneminder image](https://github.com/jantman/docker-zoneminder), then you will need to run zoneminder with ``--ipc="shareable"`` and this container with ``--ipc="container:name-of-zm-container"``; this is to allow the collector in this container to read from ZM's shared memory. If you are running ZoneMinder directly on the host, run this container with ``--ipc="host"`` (which is probably a security risk). This container **must run on the same machine as zoneminder** in order to access shared memory. 

```
docker run -p 8080:8080 \
    -e ZM_API_URL=http://zm/api \
    jantman/zoneminder-prometheus-exporter:latest
```

### Known Issues and Limitations

* This does not currently support any sort of authentication for ZoneMinder. I don't use the built-in auth.
* I'm using the [pyzm](https://github.com/ZoneMinder/pyzm) package since it's already written. It is emphatically non-Pythonic, so if you attempt to use the [main.py](main.py) python module on its own or do any development work, be aware of that. This is up to and including ignoring Python's built-in `logging` library and implementing its own non-compatible logging layer. There's also a lot of incorrect documentation, especially about types. Be warned.

### Environment Variables

* `ZM_API_URL` (**required**) - ZoneMinder API URL, e.g. `http://zmhost/zm/api`

### Debugging

For debugging, append `-vv` to your `docker run` command, to run the entrypoint with debug-level logging.

## Development

Clone the repo, then in your clone:

```
python3 -mvenv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Release Process

Tag the repo. [GitHub Actions](https://github.com/jantman/prometheus-synology-api-exporter/actions) will run a Docker build, push to Docker Hub and GHCR (GitHub Container Registry), and create a release on the repo.
