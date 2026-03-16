# OpenClaw Unified Service for MiroFish

Single-port service combining Zep Adapter + LLM Proxy for Railway deployment.

## 🎯 Why Unified?

Railway only exposes **one public port**. This service runs both on the same port with different routes.

## 🚀 Quick Deploy

1. **Connect GitHub repo** to Railway
2. **Add environment variables:**
   ```
   DATABASE_URL=postgresql://postgres:... (your Supabase URL)
   OLLAMA_URL=http://ollama.railway.internal:11434
   ```
3. **Deploy**

## 🔧 MiroFish Configuration

Update your `.env`:

```bash
# Memory (Zep) - uses /zep routes
ZEP_API_URL=https://your-railway-app.up.railway.app/zep
ZEP_API_KEY=not-needed

# LLM - uses /llm routes  
LLM_API_URL=https://your-railway-app.up.railway.app/llm/v1
LLM_API_KEY=not-needed
LLM_MODEL_NAME=gpt-4
```

## 📡 API Routes

### Zep Adapter (Memory)
- `POST /zep/api/v2/sessions` - Create session
- `GET /zep/api/v2/sessions/{id}` - Get session
- `POST /zep/api/v2/sessions/{id}/memory` - Add memory
- `GET /zep/api/v2/sessions/{id}/memory` - Get memories
- `POST /zep/api/v2/sessions/{id}/search` - Search memories

### LLM Proxy
- `GET /llm/v1/models` - List models
- `POST /llm/v1/chat/completions` - Chat completions
- `POST /llm/v1/embeddings` - Embeddings

### Health
- `GET /health` - Service health check

## 🧪 Testing

```bash
# Health check
curl https://your-app.up.railway.app/health

# Test Zep
curl -X POST https://your-app.up.railway.app/zep/api/v2/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test"}'

# Test LLM
curl -X POST https://your-app.up.railway.app/llm/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}'
```

## 🎉 Benefits

- ✅ Single port (Railway compatible)
- ✅ Both services share one deployment
- ✅ Unified health monitoring
- ✅ Simpler configuration
