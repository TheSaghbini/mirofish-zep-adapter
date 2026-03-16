# OpenClaw Integration for MiroFish

This repo provides two services that let MiroFish use OpenClaw infrastructure:

## 🧠 Zep Adapter (Port 5002)

Mimics Zep Cloud's REST API using OpenClaw's Supabase pgvector for agent memory.

**Endpoints:**
- `POST /api/v2/sessions` - Create session
- `POST /api/v2/sessions/{id}/memory` - Add memory
- `GET /api/v2/sessions/{id}/memory` - Get memories
- `POST /api/v2/sessions/{id}/search` - Search memories

## 🤖 LLM Proxy (Port 5003)

Exposes OpenClaw's Ollama models via OpenAI-compatible API.

**Endpoints:**
- `POST /v1/chat/completions` - Chat completions
- `POST /v1/completions` - Text completions
- `POST /v1/embeddings` - Embeddings
- `GET /v1/models` - List models

## 🚀 Quick Deploy to Railway

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
# Memory (Zep) - now uses OpenClaw
ZEP_API_URL=https://your-railway-app.up.railway.app
ZEP_API_KEY=not-needed

# LLM - now uses OpenClaw
LLM_API_URL=https://your-railway-app.up.railway.app:5003/v1
LLM_API_KEY=not-needed
LLM_MODEL_NAME=gpt-4
```

## 🎯 What This Gives You

✅ **No separate LLM API keys** - uses OpenClaw's Ollama
✅ **Shared memory** - MiroFish memories = OpenClaw memories
✅ **Unified infrastructure** - everything in one place
✅ **Cost savings** - no external API costs

## 🧪 Testing

```bash
# Test Zep Adapter
curl https://your-app.up.railway.app/health

# Test LLM Proxy
curl https://your-app.up.railway.app:5003/v1/models

# Test chat completion
curl -X POST https://your-app.up.railway.app:5003/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```
