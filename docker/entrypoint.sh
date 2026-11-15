#!/bin/bash

ENV_FILE="/app/.env"

> "$ENV_FILE"

[ -n "$TARGET_ENDPOINT" ] && echo "TARGET_ENDPOINT=$TARGET_ENDPOINT" >> "$ENV_FILE"
[ -n "$TARGET_IPV4" ] && echo "TARGET_IPV4=$TARGET_IPV4" >> "$ENV_FILE"
[ -n "$TARGET_IPV6" ] && echo "TARGET_IPV6=$TARGET_IPV6" >> "$ENV_FILE"
[ -n "$ALERT_URL" ] && echo "ALERT_URL=$ALERT_URL" >> "$ENV_FILE"
[ -n "$AUTH_HASH" ] && echo "AUTH_HASH=$AUTH_HASH" >> "$ENV_FILE"
[ -n "$LOCATION" ] && echo "LOCATION=$LOCATION" >> "$ENV_FILE"
[ -n "$CHECK_INTERVAL" ] && echo "CHECK_INTERVAL=$CHECK_INTERVAL" >> "$ENV_FILE"

if [ -n "$DOMAIN_NAME" ] && [ -n "$DNS_NAME" ]; then
    (
        while true; do
            uv run r53_updater.py
            sleep "${UPDATE_INTERVAL:-120}"
        done
    ) &
fi

exec uv run main.py
