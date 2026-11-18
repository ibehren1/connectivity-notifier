# Connectivity Notifier

A lightweight Python application that monitors IPv4 and IPv6 connectivity to a target host and posts alerts to a monitoring endpoint when the connection state changes.

## Features

- Monitors both IPv4 and IPv6 connectivity via ICMP ping
- Resolves a hostname to automatically determine IPv4/IPv6 targets
- Gracefully handles single-stack environments (IPv4-only or IPv6-only)
- Queues alerts and retries delivery on failure
- Posts state change notifications to a configurable HTTP alerting endpoint
- Runs as a Docker container with multi-architecture support (ARM64/AMD64)

## Requirements

- Python 3.12.8+
- [uv](https://docs.astral.sh/uv/) package manager

## Quick Start

1. Copy the example environment file and configure it:

```bash
cp .env.example .env
```

2. Edit `.env` with your settings.

3. Run the application:

```bash
uv run main.py
```

## Configuration

Configuration is managed via environment variables or a `.env` file in the working directory.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TARGET_ENDPOINT` | No | — | Hostname to resolve for IPv4/IPv6 targets (preferred over explicit IPs) |
| `TARGET_IPV4` | No* | — | IPv4 address to monitor |
| `TARGET_IPV6` | No* | — | IPv6 address to monitor |
| `ALERT_URL` | Yes | — | URL of the monitoring/alerting endpoint |
| `AUTH_HASH` | Yes | — | Authentication hash for the alert API |
| `LOCATION` | No | `Behrens` | Location label included in alert messages |
| `CHECK_INTERVAL` | No | `30` | Seconds between connectivity checks |
| `DOMAIN_NAME` | No | — | Route53 hosted zone for the DNS updater (e.g. `example.com`) |
| `DNS_NAME` | No | — | Record name kept pointed at the current public IPv4 (A) and router WAN IPv6 (AAAA), e.g. `gateway.example.com` |
| `UPDATE_INTERVAL` | No | `120` | Seconds between Route53 updater runs |
| `PROBE_LOCATION` | No | `Chicago` | Globalping location for the traceroute that finds the router WAN IPv6. Keep it near your ISP: traceroutes stop at 20 hops, so far-away probes never reach you |
| `AWS_PROFILE` | No | `default` | Profile to use from `~/.aws/credentials` |
| `AWS_ACCESS_KEY_ID` | No | — | AWS credentials for Route53, overrides `~/.aws` |
| `AWS_SECRET_ACCESS_KEY` | No | — | AWS credentials for Route53, overrides `~/.aws` |

\* At least one of `TARGET_ENDPOINT`, `TARGET_IPV4`, or `TARGET_IPV6` must be set.

In the container, the Route53 updater (`r53_updater.py`) runs in the background every `UPDATE_INTERVAL` seconds when both `DOMAIN_NAME` and `DNS_NAME` are set. When it changes a Route53 record, it posts an alert to `ALERT_URL`. The compose file mounts the host's `~/.aws` read-only so the updater can use the credentials stored there.

## Docker

### Build

Build multi-architecture images using the provided build script:

```bash
make build
```

This requires `DOCKER_USER` and `DOCKER_PAT` environment variables to be set for registry authentication.

### Run with Docker Compose

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d
```

The compose configuration includes an IPv6-enabled network to support dual-stack connectivity testing from within the container.

### Run with Docker directly

```bash
docker run -e TARGET_ENDPOINT=example.com \
  -e ALERT_URL=https://monitoring.example.com/alert \
  -e AUTH_HASH=your_hash_here \
  -e LOCATION=MyLocation \
  connectivity-notifier
```

## Alert Format

When connectivity goes **down**:

```
{location} {protocol} connectivity to `{host}` is down.  Please check! `{timestamp}`
```

When connectivity is **restored**:

```
{location} {protocol} connectivity restored. `{timestamp}`
```

Alerts are sent as JSON POST requests:

```json
{
  "message": "Behrens IPv6 connectivity to `2001:db8::1` is down.  Please check! `Wed May 14 12:00:00 2026`",
  "authHash": "your_auth_hash"
}
```

## Project Structure

```
├── main.py                  # Application entry point
├── pyproject.toml           # Project metadata and dependencies
├── .env.example             # Example environment configuration
├── Makefile                 # Build targets
├── docker/
│   ├── Dockerfile           # Container image definition
│   ├── docker-compose.yml   # Compose configuration
│   └── entrypoint.sh        # Container entrypoint script
└── scripts/
    └── build.sh             # Multi-arch Docker build script
```

## License

MIT License. See [LICENSE](LICENSE) for details.
