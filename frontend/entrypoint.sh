#!/bin/sh
set -eu
# Works with both Kubernetes DNS and Docker's local DNS.
DNS_RESOLVER="${DNS_RESOLVER:-$(awk '/^nameserver/ {print $2; exit}' /etc/resolv.conf)}"
export DNS_RESOLVER
envsubst '${API_HOST} ${API_PORT} ${DNS_RESOLVER}' \
    < /etc/nginx/lab.conf.template > /tmp/nginx.conf
exec "$@"
