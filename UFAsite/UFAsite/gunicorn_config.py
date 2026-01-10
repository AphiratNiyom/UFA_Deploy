# UFAsite/gunicorn_config.py
import multiprocessing
import os

# Timeout settings
timeout = 120  # เพิ่ม timeout เป็น 120 วินาที
graceful_timeout = 120
keepalive = 5

# Worker settings
workers = 1  # ใช้ 1 worker สำหรับ free tier
worker_class = 'sync'
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Preload app
preload_app = True

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Optimize for low memory
def when_ready(server):
    # ลด memory footprint
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    os.environ['MKL_NUM_THREADS'] = '1'
    os.environ['OMP_NUM_THREADS'] = '1'