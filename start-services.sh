#!/bin/bash
# Start both Zep adapter and LLM proxy

echo "🚀 Starting OpenClaw Services for MiroFish..."

# Start LLM Proxy in background
echo "   Starting LLM Proxy on port 5003..."
python3 llm-proxy.py &
LLM_PID=$!

# Start Zep Adapter in foreground (main process)
echo "   Starting Zep Adapter on port 5002..."
python3 app.py &
ZEP_PID=$!

echo ""
echo "✅ Both services running:"
echo "   - Zep Adapter: http://localhost:5002"
echo "   - LLM Proxy: http://localhost:5003"
echo ""

# Wait for both processes
wait $LLM_PID $ZEP_PID
