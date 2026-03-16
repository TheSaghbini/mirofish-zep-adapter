FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY unified-service.py app.py

ENV PORT=5002
ENV PYTHONUNBUFFERED=1

EXPOSE 5002

CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--workers", "4", "--timeout", "300", "app:app"]
