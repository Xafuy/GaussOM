"""Gunicorn 进程配置示例（生产按 CPU/内存调 workers）。"""
bind = "0.0.0.0:8000"
workers = 3
threads = 2
timeout = 120
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
capture_output = True
