#
# MIT License
#
#  (C) Copyright 2025 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#

"""Gunicorn settings for cray-rrs-api"""
import os

# Server socket
bind = "0.0.0.0:80"

# Worker processes
workers = int(os.environ.get("GUNICORN_WORKERS", 4))

# Worker class - use gthread for I/O bound API operations
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gthread")

# Threads per worker (only applies to gthread worker class)
threads = int(os.environ.get("GUNICORN_THREADS", 2))

# Worker timeout - reasonable for API operations
timeout = int(os.environ.get("GUNICORN_WORKER_TIMEOUT", 120))  # 2 minutes

# Preload application for better performance
preload_app = True

# Worker recycling - prevents memory leaks in long-running services
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", 100))

# Logging
accesslog = "-"  # stdout
errorlog = "-"  # stderr
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info").lower()

# Performance
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", 5))
