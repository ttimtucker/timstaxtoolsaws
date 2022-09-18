bind = "0.0.0.0:5000"
workers = 3
# Access log - records incoming HTTP requests
accesslog = "/home/ubuntu/hub/gunicorn.access.log"
# Error log - records Gunicorn server goings-on
errorlog = "/home/ubuntu/hub/gunicorn.error.log"
# Whether to send Django output to the error log
capture_output = True
# How verbose the Gunicorn error logs should be
loglevel = "debug"
timeout=60
worker_class = "gevent"
pidfile="/home/ubuntu/hub/gunicorn.pid"

