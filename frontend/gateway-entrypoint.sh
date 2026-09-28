#!/bin/sh
set -eu

# The host-facing bridge permits localhost port publishing. Remove its route
# before starting Nginx. Compose points external DNS at local loopback while
# Docker's embedded resolver continues to resolve internal service names.
ip route del default
cp /etc/nginx/gateway.conf /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
