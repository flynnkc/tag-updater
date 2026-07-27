FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY entrypoint.py ./
COPY modules ./modules

ENTRYPOINT ["python", "/app/entrypoint.py"]
