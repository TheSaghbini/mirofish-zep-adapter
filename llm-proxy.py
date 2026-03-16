#!/usr/bin/env python3
"""
OpenClaw LLM Proxy for MiroFish
Exposes Ollama models via OpenAI-compatible API
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
import os
import json
import time
import uuid

app = Flask(__name__)
CORS(app)

# OpenClaw Ollama configuration
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://ollama.railway.internal:11434')
DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL', 'kimi-k2.5:cloud')

# Available models (mapped to Ollama)
MODELS = {
    'gpt-4': 'kimi-k2.5:cloud',
    'gpt-3.5-turbo': 'glm-5:cloud',
    'qwen-plus': 'kimi-k2.5:cloud',  # MiroFish recommended
    'default': DEFAULT_MODEL
}

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get('models', [])
            return jsonify({
                "status": "ok",
                "service": "openclaw-llm-proxy",
                "ollama_connected": True,
                "available_models": len(models)
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "ollama_connected": False,
            "error": str(e)
        }), 503

@app.route('/v1/models', methods=['GET'])
def list_models():
    """List available models (OpenAI compatible)"""
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": "gpt-4",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "openclaw"
            },
            {
                "id": "gpt-3.5-turbo",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "openclaw"
            },
            {
                "id": "qwen-plus",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "openclaw"
            }
        ]
    })

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """Chat completions endpoint (OpenAI compatible)"""
    data = request.json or {}
    
    model = data.get('model', 'gpt-4')
    messages = data.get('messages', [])
    stream = data.get('stream', False)
    temperature = data.get('temperature', 0.7)
    max_tokens = data.get('max_tokens', 2000)
    
    # Map to Ollama model
    ollama_model = MODELS.get(model, DEFAULT_MODEL)
    
    # Convert messages to Ollama format
    prompt = "\n".join([
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages
    ])
    
    try:
        if stream:
            # Streaming response
            def generate():
                ollama_resp = requests.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": ollama_model,
                        "prompt": prompt,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens
                        }
                    },
                    stream=True,
                    timeout=300
                )
                
                for line in ollama_resp.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            if 'response' in chunk:
                                yield f"data: {json.dumps({
                                    'id': str(uuid.uuid4()),
                                    'object': 'chat.completion.chunk',
                                    'created': int(time.time()),
                                    'model': model,
                                    'choices': [{
                                        'index': 0,
                                        'delta': {'content': chunk['response']},
                                        'finish_reason': None
                                    }]
                                })}\n\n"
                        except:
                            pass
                
                yield f"data: {json.dumps({'choices': [{'finish_reason': 'stop'}]})}\n\n"
                yield "data: [DONE]\n\n"
            
            return Response(generate(), mimetype='text/plain')
        
        else:
            # Non-streaming response
            ollama_resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=300
            )
            
            ollama_data = ollama_resp.json()
            
            return jsonify({
                "id": str(uuid.uuid4()),
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": ollama_data.get('response', '')
                    },
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

@app.route('/v1/completions', methods=['POST'])
def completions():
    """Legacy completions endpoint"""
    data = request.json or {}
    prompt = data.get('prompt', '')
    model = data.get('model', 'gpt-4')
    
    ollama_model = MODELS.get(model, DEFAULT_MODEL)
    
    try:
        ollama_resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": ollama_model,
                "prompt": prompt,
                "stream": False
            },
            timeout=300
        )
        
        ollama_data = ollama_resp.json()
        
        return jsonify({
            "id": str(uuid.uuid4()),
            "object": "text_completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "text": ollama_data.get('response', ''),
                "index": 0,
                "finish_reason": "stop"
            }]
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/v1/embeddings', methods=['POST'])
def embeddings():
    """Embeddings endpoint"""
    data = request.json or {}
    input_text = data.get('input', '')
    model = data.get('model', 'text-embedding-ada-002')
    
    try:
        # Use Ollama for embeddings
        ollama_resp = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={
                "model": "mxbai-embed-large:latest",
                "prompt": input_text if isinstance(input_text, str) else input_text[0]
            },
            timeout=30
        )
        
        ollama_data = ollama_resp.json()
        embedding = ollama_data.get('embedding', [])
        
        return jsonify({
            "object": "list",
            "data": [{
                "object": "embedding",
                "embedding": embedding,
                "index": 0
            }],
            "model": model,
            "usage": {
                "prompt_tokens": len(input_text.split()) if isinstance(input_text, str) else 0,
                "total_tokens": len(input_text.split()) if isinstance(input_text, str) else 0
            }
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('LLM_PROXY_PORT', 5003))
    print(f"🚀 OpenClaw LLM Proxy starting on port {port}")
    print(f"   Ollama URL: {OLLAMA_URL}")
    print(f"   Default model: {DEFAULT_MODEL}")
    app.run(host='0.0.0.0', port=port)
