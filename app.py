#!/usr/bin/env python3
"""
Zep Cloud API Adapter for OpenClaw Memory
Mimics Zep's REST API using Supabase pgvector
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
import json
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)

# Database configuration from environment
DB_URL = os.environ.get('DATABASE_URL', 'postgresql://user:pass@localhost:5432/db')

def get_db_connection():
    """Get database connection to OpenClaw Supabase"""
    return psycopg2.connect(DB_URL)

def init_db():
    """Initialize database tables if they don't exist"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create mirofish_sessions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mirofish_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Create mirofish_memories table (links to OpenClaw agent_memory)
    # Note: agent_memory.id is UUID, so we store it as TEXT without FK constraint
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

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint - also tests DB connection"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM agent_memory WHERE is_active = TRUE')
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({
            "status": "ok",
            "service": "zep-openclaw-adapter",
            "openclaw_memories": count,
            "database": "connected"
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/v2/sessions', methods=['POST'])
def create_session():
    """Create a new session in OpenClaw"""
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

@app.route('/api/v2/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get session info from OpenClaw"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM mirofish_sessions WHERE id = %s
    """, (session_id,))
    
    session = cur.fetchone()
    cur.close()
    conn.close()
    
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify(dict(session))

@app.route('/api/v2/sessions/<session_id>/memory', methods=['POST'])
def add_memory(session_id):
    """Add memory to session - saves to OpenClaw agent_memory"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check session exists
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
        # First, save to OpenClaw's agent_memory table
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
        
        agent_memory_id = cur.fetchone()[0]
        
        # Then link in mirofish_memories
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

@app.route('/api/v2/sessions/<session_id>/memory', methods=['GET'])
def get_memory(session_id):
    """Get memories for session from OpenClaw"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT m.id, m.session_id, m.content, m.role, m.created_at,
               am.confidence, am.tags
        FROM mirofish_memories m
        JOIN agent_memory am ON m.agent_memory_id = am.id
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

@app.route('/api/v2/sessions/<session_id>/search', methods=['POST'])
def search_session(session_id):
    """Search within session using OpenClaw's semantic search"""
    data = request.json or {}
    query = data.get('query', data.get('text', ''))
    limit = data.get('limit', 5)
    
    if not query:
        return jsonify({'error': 'Query required'}), 400
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Use OpenClaw's semantic search via pgvector
        # First get the embedding for the query (simplified - using text search for now)
        cur.execute("""
            SELECT m.id, m.content, m.role, m.created_at,
                   similarity(m.content, %s) as sim
            FROM mirofish_memories m
            JOIN agent_memory am ON m.agent_memory_id = am.id
            WHERE m.session_id = %s AND am.is_active = TRUE
            ORDER BY sim DESC
            LIMIT %s
        """, (query, session_id, limit))
        
        results = cur.fetchall()
    except Exception as e:
        # Fallback to simple ILIKE search
        cur.execute("""
            SELECT m.id, m.content, m.role, m.created_at, 0.8 as sim
            FROM mirofish_memories m
            JOIN agent_memory am ON m.agent_memory_id = am.id
            WHERE m.session_id = %s 
              AND am.is_active = TRUE
              AND m.content ILIKE %s
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

@app.route('/api/v2/sessions/<session_id>/facts', methods=['GET'])
def get_facts(session_id):
    """Get extracted facts (semantic memories) from OpenClaw"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT am.id, am.title, am.content, am.created_at
        FROM agent_memory am
        WHERE am.agent_id = %s 
          AND am.memory_type = 'semantic'
          AND am.is_active = TRUE
        ORDER BY am.created_at DESC
    """, (f'mirofish-{session_id}',))
    
    facts = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify({
        'facts': [dict(f) for f in facts],
        'count': len(facts)
    })

if __name__ == '__main__':
    # Initialize database tables
    init_db()
    
    port = int(os.environ.get('PORT', 5002))
    print(f"🚀 Zep-OpenClaw Adapter starting on port {port}")
    print(f"   Connected to OpenClaw Supabase")
    app.run(host='0.0.0.0', port=port)
