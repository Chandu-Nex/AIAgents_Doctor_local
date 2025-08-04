import uvicorn
import threading
import time
import logging
from config import Config

# Import all API modules
from chunk_api import app as chunk_app
from embeddings_api import app as embeddings_app
from knowledgegraph_api import app as kg_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_api(app, port, name):
    """Run a FastAPI app on specified port"""
    try:
        uvicorn.run(app, host=Config.HOST, port=port, log_level="info")
    except Exception as e:
        logger.error(f"Failed to start {name} API on port {port}: {e}")

def main():
    """Start all RAG APIs"""
    # Validate configuration
    try:
        Config.validate()
        logger.info("✅ Configuration validated successfully")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        return

    # Start APIs in separate threads
    apis = [
        (chunk_app, Config.CHUNK_API_PORT, "Chunk API"),
        (embeddings_app, Config.EMBEDDINGS_API_PORT, "Embeddings API"),
        (kg_app, Config.KNOWLEDGE_GRAPH_API_PORT, "Knowledge Graph API")
    ]

    threads = []
    for app, port, name in apis:
        thread = threading.Thread(target=run_api, args=(app, port, name), daemon=True)
        thread.start()
        threads.append(thread)
        logger.info(f"🚀 Started {name} on port {port}")
        time.sleep(1)  # Small delay between starts

    logger.info("🎉 All RAG APIs are running!")
    logger.info(f"📡 Chunk API: http://localhost:{Config.CHUNK_API_PORT}")
    logger.info(f"🧠 Embeddings API: http://localhost:{Config.EMBEDDINGS_API_PORT}")
    logger.info(f"🔗 Knowledge Graph API: http://localhost:{Config.KNOWLEDGE_GRAPH_API_PORT}")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down RAG APIs...")

if __name__ == "__main__":
    main() 