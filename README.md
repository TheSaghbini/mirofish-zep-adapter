# Zep-OpenClaw Adapter

Mimics Zep Cloud's REST API using OpenClaw's Supabase pgvector memory.

## Quick Deploy to Railway

1. **Create GitHub repo** with these files
2. **Connect Railway** to that repo
3. **Set environment variables** in Railway:
   - `DATABASE_URL` = your Supabase connection string
4. **Deploy**

## MiroFish Configuration

Update `.env`:
```
ZEP_API_URL=https://your-railway-app.up.railway.app
ZEP_API_KEY=not-needed
```

## Endpoints

- `POST /api/v2/sessions` - Create session
- `POST /api/v2/sessions/{id}/memory` - Add memory
- `GET /api/v2/sessions/{id}/memory` - Get memories
- `POST /api/v2/sessions/{id}/search` - Search memories

## Testing

```bash
curl https://your-app.up.railway.app/health
```
