FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py llm-proxy.py .

# Environment variables
ENV PORT=5002
ENV LLM_PROXY_PORT=5003
ENV OLLAMA_URL=http://ollama.railway.internal:11434
ENV PYTHONUNBUFFERED=1

EXPOSE 5002 5003

# Run both services using a process manager or script
COPY start-services.sh .
RUN chmod +x start-services.sh

CMD ["./start-services.sh"]
