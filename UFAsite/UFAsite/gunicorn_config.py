timeout = 120  # เพิ่มเป็น 120 วินาที
workers = 1
worker_class = 'sync'
max_requests = 1000
max_requests_jitter = 50
preload_app = True  # โหลด app ก่อน fork workers