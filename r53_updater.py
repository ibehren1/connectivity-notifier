
#!/usr/bin/env python3

import boto3
import ipaddress
import os
import requests
import time

from botocore.exceptions import ClientError
from datetime import datetime
from zoneinfo import ZoneInfo

from main import load_dotenv, send_alert

load_dotenv()

domain_name = os.environ.get("DOMAIN_NAME")
dns_name = os.environ.get("DNS_NAME")

if not domain_name or not dns_name:
    raise SystemExit("DOMAIN_NAME and DNS_NAME env vars are required")

alert_url = os.environ.get("ALERT_URL")
auth_hash = os.environ.get("AUTH_HASH")
location = os.environ.get("LOCATION", "Behrens")

globalping_url = 'https://api.globalping.io/v1/measurements'

route53 = boto3.client('route53')


def get_current_ipv4():
    # api4.ipify.org only has an A record, so this request always goes out over IPv4.
    r = requests.get('https://api4.ipify.org', timeout=10)
    r.raise_for_status()
    return str(ipaddress.IPv4Address(r.text.strip()))


def get_host_ipv6():
    # api6.ipify.org only has an AAAA record, so this request always goes out over IPv6.
    r = requests.get('https://api6.ipify.org', timeout=10)
    r.raise_for_status()
    return str(ipaddress.IPv6Address(r.text.strip()))


def get_router_wan_ipv6(host_ipv6):
    # IPv6 has no NAT, so the router's WAN address can't be seen from the LAN.
    # Instead, traceroute from an external probe back to this host: the router
    # answers the hop before us with ICMPv6 Time Exceeded sent out its WAN
    # interface, so that hop's address is the router's WAN address.
    r = requests.post(globalping_url, json={
        'type': 'traceroute',
        'target': host_ipv6,
        'limit': 1,
        'locations': [{'magic': 'world'}],
        'measurementOptions': {'protocol': 'ICMP'},
    }, timeout=10)
    r.raise_for_status()
    measurement_id = r.json()['id']

    deadline = time.time() + 30
    while True:
        r = requests.get(globalping_url + '/' + measurement_id, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data['status'] != 'in-progress':
            break
        if time.time() > deadline:
            raise ValueError('Timed out waiting for traceroute.')
        time.sleep(1)

    hops = data['results'][0]['result']['hops']
    addresses = [hop['resolvedAddress'] for hop in hops if hop.get('resolvedAddress')]
    addresses = [str(ipaddress.ip_address(a)) for a in addresses]
    if host_ipv6 in addresses:
        addresses = addresses[:addresses.index(host_ipv6)]
    if not addresses:
        raise ValueError('Traceroute returned no hops before this host.')

    router_ip = ipaddress.ip_address(addresses[-1])
    host_network = ipaddress.ip_network(host_ipv6 + '/64', strict=False)
    if router_ip.version != 6 or not router_ip.is_global or router_ip in host_network:
        raise ValueError('Hop before this host (' + str(router_ip) + ') is not a router WAN address.')
    return str(router_ip)


def get_hosted_zone_id():
    response = route53.list_hosted_zones_by_name(DNSName=domain_name + '.')
    hosted_zone_id = response['HostedZones'][0]['Id']
    hosted_zone_id = hosted_zone_id.split("/", 2)[2]
    return hosted_zone_id


def get_dns_ip(record_type):
    response = route53.list_resource_record_sets(
        HostedZoneId=get_hosted_zone_id(),
        StartRecordName=dns_name,
        StartRecordType=record_type,
        MaxItems='1'
    )
    # Route53 returns the next record in the zone if the requested one doesn't exist.
    records = response['ResourceRecordSets']
    if not records or records[0]['Name'].rstrip('.') != dns_name or records[0]['Type'] != record_type:
        return None
    return records[0]['ResourceRecords'][0]['Value']


def update_dns_record(current_ip, record_type):
    try:
        route53.change_resource_record_sets(
            HostedZoneId=get_hosted_zone_id(),
            ChangeBatch={
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': dns_name,
                            'Type': record_type,
                            'TTL': 60,
                            'ResourceRecords': [
                                {
                                    'Value': current_ip
                                },
                            ],
                        }
                    },
                ]
            }
        )
        print(dns_name + ' ' + record_type + ' updated to ' + current_ip)
        return True
    except ClientError:
        print('Failed to update Route53 ' + record_type + ' record.')
        return False


def post_update_alert(old_ip, new_ip, record_type):
    if not alert_url or not auth_hash:
        return
    date = datetime.now(ZoneInfo("America/Chicago")).strftime("%c")
    message = f"🔄 {location} `{dns_name}` {record_type} record updated from `{old_ip}` to `{new_ip}`. `{date}`"
    if send_alert(alert_url, auth_hash, message):
        print('Alert sent: ' + message)
    else:
        print('Alert delivery failed: ' + message)


def update_if_changed(current_ip, record_type):
    current_dns_ip = get_dns_ip(record_type)
    if current_dns_ip and ipaddress.ip_address(current_ip) == ipaddress.ip_address(current_dns_ip):
        print('No ' + record_type + ' update needed.')
    elif update_dns_record(current_ip, record_type):
        post_update_alert(current_dns_ip or 'none', current_ip, record_type)


def main():
    update_if_changed(get_current_ipv4(), 'A')

    try:
        router_ipv6 = get_router_wan_ipv6(get_host_ipv6())
    except (requests.RequestException, ValueError, KeyError, IndexError) as e:
        print('Skipping AAAA update: ' + str(e))
        return
    print('Router WAN IPv6: ' + router_ipv6)
    update_if_changed(router_ipv6, 'AAAA')


if __name__ == "__main__":
    main()
