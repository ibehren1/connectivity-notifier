import json
import os
import socket
from collections import deque
from datetime import datetime
from pathlib import Path
import time

from icmplib import ping as icmp_ping
import urllib3


def load_dotenv(path: Path = Path(".env")):
    if not path.is_file():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            os.environ.setdefault(key, value)


def resolve_targets(endpoint: str) -> tuple[str | None, str | None]:
    ipv4 = None
    ipv6 = None
    results = socket.getaddrinfo(endpoint, None)
    for family, _, _, _, sockaddr in results:
        if family == socket.AF_INET and not ipv4:
            ipv4 = sockaddr[0]
        elif family == socket.AF_INET6 and not ipv6:
            ipv6 = sockaddr[0]
    if not ipv4 and not ipv6:
        raise SystemExit(f"Could not resolve any address for {endpoint}")
    return ipv4, ipv6


def get_config():
    load_dotenv()

    endpoint = os.environ.get("TARGET_ENDPOINT")
    alert_url = os.environ.get("ALERT_URL")
    auth_hash = os.environ.get("AUTH_HASH")
    location = os.environ.get("LOCATION", "Behrens")
    interval = int(os.environ.get("CHECK_INTERVAL", "30"))

    if endpoint:
        ipv4, ipv6 = resolve_targets(endpoint)
    else:
        ipv4 = os.environ.get("TARGET_IPV4")
        ipv6 = os.environ.get("TARGET_IPV6")
        if not ipv4 and not ipv6:
            raise SystemExit("TARGET_IPV4 and/or TARGET_IPV6 env var is required (or set TARGET_ENDPOINT)")

    if not alert_url:
        raise SystemExit("ALERT_URL env var is required")
    if not auth_hash:
        raise SystemExit("AUTH_HASH env var is required")

    return ipv4, ipv6, alert_url, auth_hash, location, interval


def ping(host: str) -> bool:
    result = icmp_ping(host, count=1, timeout=5, privileged=False)
    return result.is_alive


def send_alert(alert_url: str, auth_hash: str, message: str) -> bool:
    try:
        http = urllib3.PoolManager()
        payload = json.dumps({"message": message, "authHash": auth_hash})
        resp = http.request(
            "POST",
            alert_url,
            body=payload,
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )
        return 200 <= resp.status < 300
    except Exception:
        return False


def drain_alert_queue(queue: deque, alert_url: str, auth_hash: str):
    while queue:
        message = queue[0]
        if send_alert(alert_url, auth_hash, message):
            queue.popleft()
            print(f"Alert sent: {message}")
        else:
            print(f"Alert delivery failed, {len(queue)} message(s) queued")
            break


def format_down_message(location: str, protocol: str, host: str) -> str:
    date = datetime.now().strftime("%c")
    return f"⚠️  {location} {protocol} connectivity to `{host}` is down.  Please check! `{date}`"


def format_up_message(location: str, protocol: str) -> str:
    date = datetime.now().strftime("%c")
    return f"✅ {location} {protocol} connectivity restored. `{date}`"


def main():
    ipv4, ipv6, alert_url, auth_hash, location, interval = get_config()

    targets = []
    if ipv4:
        targets.append(("IPv4", ipv4))
    if ipv6:
        targets.append(("IPv6", ipv6))

    print(f"Monitoring {', '.join(f'{p}={h}' for p, h in targets)} every {interval}s")

    state: dict[str, bool | None] = {proto: None for proto, _ in targets}
    alert_queue: deque[str] = deque()

    while True:
        for proto, host in targets:
            up = ping(host)
            status = "up" if up else "down"
            print(f"Ping {proto} ({host}): {status}")

            if up != state[proto]:
                if up:
                    msg = format_up_message(location, proto)
                else:
                    msg = format_down_message(location, proto, host)
                print(msg)
                if state[proto] is not None:
                    alert_queue.append(msg)
                state[proto] = up

        drain_alert_queue(alert_queue, alert_url, auth_hash)

        time.sleep(interval)


if __name__ == "__main__":
    main()
