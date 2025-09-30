import multiprocessing

# Server socket
bind = "0.0.0.0:9090"
backlog = 2048

# Worker processes
workers = 2
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 300  # 5 minutes
graceful_timeout = 30
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "api_gateway"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (optional)
# keyfile = None
# certfile = None

# Server hooks
def pre_fork(server, worker):
    server.log.info("Server pre-fork")

def post_fork(server, worker):
    server.log.info("Server post-fork")

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal")