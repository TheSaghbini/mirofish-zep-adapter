#!/usr/bin/env python3
"""
OpenClaw Unified Service for MiroFish
Combines Zep Adapter + LLM Proxy on single port
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import uuid
import json
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuration
DB_URL = os.environ.get('DATABASE_URL', 'postgresql://user:pass@localhost:5432/db')
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://ollama.railway.internal:11434')
DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL', 'kimi-k2.5:cloud')

# Model mapping
MODELS = {
    'gpt-4': 'kimi-k2.5:cloud',
    'gpt-3.5-turbo': 'glm-5:cloud',
    'qwen-plus': 'kimi-k2.5:cloud',
    'default': DEFAULT_MODEL
}

def get_db_connection():
    return psycopg2.connect(DB_URL)

def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mirofish_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mirofish_memories (
            id TEXT PRIMARY KEY,
            session_id TEXT REFERENCES mirofish_sessions(id),
            agent_memory_id TEXT,
            content TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()

# ==================== HEALTH & INFO ====================

@app.route('/health', methods=['GET'])
def health():
    """Health check for both services"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM agent_memory WHERE is_active = TRUE')
        memory_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        return jsonify({
            "status": "ok",
            "service": "openclaw-unified",
            "zep_adapter": "enabled",
            "llm_proxy": "enabled",
            "openclaw_memories": memory_count,
            "database": "connected"
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# ==================== ZEP ADAPTER ROUTES ====================

@app.route('/zep/api/v2/sessions', methods=['POST'])
def zep_create_session():
    """Create session"""
    data = request.json or {}
    session_id = data.get('session_id', str(uuid.uuid4()))
    user_id = data.get('user_id', 'anonymous')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO mirofish_sessions (id, user_id)
            VALUES (%s, %s)
            ON CONFLICT (id) DO UPDATE SET updated_at = NOW()
        """, (session_id, user_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    
    return jsonify({
        'session_id': session_id,
        'user_id': user_id,
        'created_at': datetime.now().isoformat()
    }), 201

@app.route('/zep/api/v2/sessions/<session_id>', methods=['GET'])
def zep_get_session(session_id):
    """Get session"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM mirofish_sessions WHERE id = %s", (session_id,))
    session = cur.fetchone()
    cur.close()
    conn.close()
    
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify(dict(session))

@app.route('/zep/api/v2/sessions/<session_id>/memory', methods=['POST'])
def zep_add_memory(session_id):
    """Add memory"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT 1 FROM mirofish_sessions WHERE id = %s", (session_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({'error': 'Session not found'}), 404
    
    data = request.json or {}
    content = data.get('content', data.get('message', {}).get('content', ''))
    role = data.get('role', data.get('message', {}).get('role', 'user'))
    
    if not content:
        cur.close()
        conn.close()
        return jsonify({'error': 'Content required'}), 400
    
    memory_id = str(uuid.uuid4())
    
    try:
        # Save to OpenClaw agent_memory
        cur.execute("""
            INSERT INTO agent_memory (agent_id, title, content, memory_type, category, tags, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            f'mirofish-{session_id}',
            f'Session {session_id} - {role}',
            content,
            'episodic',
            'mirofish',
            json.dumps(['mirofish', session_id, role]),
            0.9
        ))
        
        agent_memory_id = str(cur.fetchone()[0])
        
        # Link in mirofish_memories
        cur.execute("""
            INSERT INTO mirofish_memories (id, session_id, agent_memory_id, content, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (memory_id, session_id, agent_memory_id, content, role))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
    
    return jsonify({
        'uuid': memory_id,
        'session_id': session_id,
        'content': content,
        'role': role,
        'created_at': datetime.now().isoformat()
    }), 201

@app.route('/zep/api/v2/sessions/<session_id>/memory', methods=['GET'])
def zep_get_memory(session_id):
    """Get memories"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT m.id, m.session_id, m.content, m.role, m.created_at
        FROM mirofish_memories m
        JOIN agent_memory am ON m.agent_memory_id = am.id::text
        WHERE m.session_id = %s AND am.is_active = TRUE
        ORDER BY m.created_at DESC
    """, (session_id,))
    
    memories = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify({
        'memories': [dict(m) for m in memories],
        'count': len(memories)
    })

@app.route('/zep/api/v2/sessions/<session_id>/search', methods=['POST'])
def zep_search(session_id):
    """Search memories"""
    data = request.json or {}
    query = data.get('query', data.get('text', ''))
    limit = data.get('limit', 5)
    
    if not query:
        return jsonify({'error': 'Query required'}), 400
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT m.id, m.content, m.role, m.created_at,
                   similarity(m.content, %s) as sim
            FROM mirofish_memories m
            JOIN agent_memory am ON m.agent_memory_id = am.id::text
            WHERE m.session_id = %s AND am.is_active = TRUE
            ORDER BY sim DESC
            LIMIT %s
        """, (query, session_id, limit))
        results = cur.fetchall()
    except:
        # Fallback to ILIKE
        cur.execute("""
            SELECT m.id, m.content, m.role, m.created_at, 0.8 as sim
            FROM mirofish_memories m
            JOIN agent_memory am ON m.agent_memory_id = am.id::text
            WHERE m.session_id = %s AND am.is_active = TRUE AND m.content ILIKE %s
            ORDER BY m.created_at DESC
            LIMIT %s
        """, (session_id, f'%{query}%', limit))
        results = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    
    return jsonify({
        'results': [dict(r) for r in results],
        'query': query,
        'count': len(results)
    })

# ==================== LLM PROXY ROUTES ====================

@app.route('/llm/v1/models', methods=['GET'])
def llm_list_models():
    """List models"""
    return jsonify({
        "object": "list",
        "data": [
            {"id": "gpt-4", "object": "model", "created": int(datetime.now().timestamp()), "owned_by": "openclaw"},
            {"id": "gpt-3.5-turbo", "object": "model", "created": int(datetime.now().timestamp()), "owned_by": "openclaw"},
            {"id": "qwen-plus", "object": "model", "created": int(datetime.now().timestamp()), "owned_by": "openclaw"}
        ]
    })

@app.route('/llm/v1/chat/completions', methods=['POST'])
def llm_chat_completions():
    """Chat completions"""
    data = request.json or {}
    model = data.get('model', 'gpt-4')
    messages = data.get('messages', [])
    stream = data.get('stream', False)
    temperature = data.get('temperature', 0.7)
    
    ollama_model = MODELS.get(model, DEFAULT_MODEL)
    prompt = "\n".join([f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}" for m in messages])
    
    try:
        if stream:
            def generate():
                resp = requests.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": ollama_model, "prompt": prompt, "stream": True, "options": {"temperature": temperature}},
                    stream=True, timeout=300
                )
                for line in resp.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            if 'response' in chunk:
                                data = {
                                    'id': str(uuid.uuid4()),
                                    'object': 'chat.completion.chunk',
                                    'created': int(datetime.now().timestamp()),
                                    'model': model,
                                    'choices': [{'index': 0, 'delta': {'content': chunk['response']}, 'finish_reason': None}]
                                }
                                yield f"data: {json.dumps(data)}\n\n"
                        except:
                            pass
                yield f"data: {json.dumps({'choices': [{'finish_reason': 'stop'}]})}\n\n"
                yield "data: [DONE]\n\n"
            return Response(generate(), mimetype='text/plain')
        
        else:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": ollama_model, "prompt": prompt, "stream": False, "options": {"temperature": temperature}},
                timeout=300
            )
            ollama_data = resp.json()
            
            return jsonify({
                "id": str(uuid.uuid4()),
                "object": "chat.completion",
                "created": int(datetime.now().timestamp()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": ollama_data.get('response', '')},
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": ollama_data.get('prompt_eval_count', 0),
                    "completion_tokens": ollama_data.get('eval_count', 0),
                    "total_tokens": ollama_data.get('prompt_eval_count', 0) + ollama_data.get('eval_count', 0)
                }
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/llm/v1/embeddings', methods=['POST'])
def llm_embeddings():
    """Embeddings"""
    data = request.json or {}
    input_text = data.get('input', '')
    
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": "mxbai-embed-large:latest", "prompt": input_text if isinstance(input_text, str) else input_text[0]},
            timeout=30
        )
        embedding = resp.json().get('embedding', [])
        
        return jsonify({
            "object": "list",
            "data": [{"object": "embedding", "embedding": embedding, "index": 0}],
            "model": "text-embedding-ada-002",
            "usage": {"prompt_tokens": 0, "total_tokens": 0}
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5002))
    print(f"🚀 OpenClaw Unified Service on port {port}")
    print(f"   Zep routes: /zep/*")
    print(f"   LLM routes: /llm/*")
    app.run(host='0.0.0.0', port=port)
