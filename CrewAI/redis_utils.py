# Updated redis_utils.py with modified search method

# File: redis_utils.py
import redis
from typing import Callable, Any, Optional
import os
from dotenv import load_dotenv
from flask import Flask, jsonify, request
import json
from crewai.memory.storage.interface import Storage

load_dotenv()
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

def publish_message(channel: str, message: str) -> None:
    """
    Publish a message to a specific Redis channel.
    """
    try:
        redis_client.publish(channel, message)
    except redis.RedisError as e:
        raise ConnectionError(f"Failed to publish message: {e}")

def subscribe_to_channel(channel: str, callback: Callable[[str], Any]) -> None:
    """
    Subscribe to a Redis channel and process messages with a callback.
   
    Note: This blocks the thread; use in a separate thread/process for non-blocking.
    """
    try:
        pubsub = redis_client.pubsub()
        pubsub.subscribe(channel)
        for item in pubsub.listen():
            if item['type'] == 'message':
                message = item['data'].decode('utf-8')
                callback(message)
    except redis.RedisError as e:
        raise ConnectionError(f"Failed to subscribe: {e}")

class RedisStorage(Storage):
    """
    Custom Redis-backed storage for CrewAI memory, ensuring persistent storage of conversations
    and knowledge. This implements the Storage interface for plug-and-play use in CrewAI's
    memory systems (e.g., LongTermMemory, ShortTermMemory, etc.).
    
    Conversations are appended to a Redis list for chronological persistence.
    Basic string-based search is provided; for advanced semantic search, consider integrating
    embeddings or Redisearch module.
    """
    def __init__(self, client=redis_client, key_prefix='crew:'):
        self.client = client
        self.key_prefix = key_prefix

    def save(self, value: str, metadata: dict = None, agent: str = None) -> None:
        """
        Save a conversation message or knowledge item to Redis persistently.
        """
        memory_data = {
            'value': value,
            'metadata': metadata or {},
            'agent': agent
        }
        key = f'{self.key_prefix}memories'
        self.client.rpush(key, json.dumps(memory_data))

    def search(self, keyword: Optional[str] = None, session_id: Optional[str] = None, agent: Optional[str] = None, user_id: Optional[int] = None, mem_type: Optional[str] = None, limit: int = 10) -> list:
        """
        Search for relevant conversations or knowledge items based on filters.
        Uses basic string matching and metadata filters; results are returned as list of dicts.
        """
        memories = self.client.lrange(f'{self.key_prefix}memories', 0, -1)
        results = []
        for mem in memories:
            data = json.loads(mem.decode('utf-8'))
            match = True
            if keyword and keyword.lower() not in str(data['value']).lower():
                match = False
            if session_id and data['metadata'].get('session_id') != session_id:
                match = False
            if agent and data['agent'] != agent:
                match = False
            if user_id is not None and data['metadata'].get('user_id') != user_id:
                match = False
            if mem_type and data['metadata'].get('type') != mem_type:
                match = False
            if match:
                results.append(data)
            if len(results) >= limit:
                break
        return results

    def reset(self) -> None:
        """
        Reset (delete) the stored conversations for a new process.
        """
        self.client.delete(f'{self.key_prefix}memories')

app = Flask(__name__)

@app.route('/publish', methods=['POST'])
def api_publish():
    data = request.get_json()
    channel = data.get('channel')
    message = data.get('message')
    if not channel or not message:
        return jsonify({'error': 'Missing channel or message'}), 400
    try:
        publish_message(channel, message)
        return jsonify({'status': 'Message published'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500