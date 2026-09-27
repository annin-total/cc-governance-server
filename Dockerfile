FROM python:3.9-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /app/data/csv

# PID 1 の Python は SIGTERM を既定で無視するので、waitress が受け取って終われる SIGINT で止める
STOPSIGNAL SIGINT

CMD ["./entry.sh"]
