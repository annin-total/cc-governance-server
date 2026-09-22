FROM python:3.9-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /app/data/csv

CMD ["./entry.sh"]
