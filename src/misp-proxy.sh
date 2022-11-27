#!/bin/bash

/usr/bin/python3 /app/misp-proxy.py /app/config.yml 2>&1 > /tmp/misp-proxy.log &