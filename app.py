#!/usr/bin/env python3
"""
Zep Cloud API Adapter for OpenClaw Memory
Mimics Zep's REST API using Supabase pgvector
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional

app = Flask(__name__)
CORS(app)

# Database configuration
DB_URL = os.environ.get('DATABASE_URL', 'postgresql://user:pass@localhost:5432/db')

# Simple in-memory storage (replace with proper DB in production)
sessions = {}
memories = {}

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "zep-openclaw-adapter"})

@app.route('/api/v2/sessions', methods=['POST'])
def create_session():
    """Create a new session"""
    data = request.json or {}
    session_id = data.get('session_id', str(uuid.uuid4()))
    user_id = data.get('user_id', 'anonymous')
    
    sessions[session_id] = {
        'id': session_id,
        'user_id': user_id,
        'created_at': datetime.now().isoformat(),
        'memory_count': 0
    }
    
    return jsonify({
        'session_id': session_id,
        'user_id': user_id,
        'created_at': sessions[session_id]['created_at']
    }), 201

@app.route('/api/v2/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get session info"""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify(sessions[session_id])

@app.route('/api/v2/sessions/<session_id>/memory', methods=['POST'])
def add_memory(session_id):
    """Add memory to session"""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    data = request.json or {}
    content = data.get('content', data.get('message', {}).get('content', ''))
    role = data.get('role', data.get('message', {}).get('role', 'user'))
    
    if not content:
        return jsonify({'error': 'Content required'}), 400
    
    memory_id = str(uuid.uuid4())
    memories[memory_id] = {
        'uuid': memory_id,
        'session_id': session_id,
        'content': content,
        'role': role,
        'created_at': datetime.now().isoformat()
    }
    
    sessions[session_id]['memory_count'] += 1
    
    return jsonify(memories[memory_id]), 201

@app.route('/api/v2/sessions/<session_id>/memory', methods=['GET'])
def get_memory(session_id):
    """Get memories for session"""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session_memories = [
        m for m in memories.values()
        if m['session_id'] == session_id
    ]
    
    return jsonify({
        'memories': session_memories,
        'count': len(session_memories)
    })

@app.route('/api/v2/sessions/<session_id>/search', methods=['POST'])
def search_session(session_id):
    """Search within session"""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    data = request.json or {}
    query = data.get('query', data.get('text', ''))
    
    # Simple keyword search (replace with semantic search)
    results = [
        m for m in memories.values()
        if m['session_id'] == session_id and query.lower() in m['content'].lower()
    ]
    
    return jsonify({
        'results': results,
        'query': query,
        'count': len(results)
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    print(f"🚀 Zep-OpenClaw Adapter starting on port {port}")
    app.run(host='0.0.0.0', port=port)
