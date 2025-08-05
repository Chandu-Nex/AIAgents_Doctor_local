import json
import numpy as np
import logging
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import os
from datetime import datetime

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# Load embedding model
MODEL_NAME = 'pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb'
logging.info(f"Loading embedding model: {MODEL_NAME}")
model = SentenceTransformer(MODEL_NAME)

# File paths
CHUNK_FILE = "./RAG/chunks/20250804_221234_chunks.json"
EMBED_DIR = "./RAG/embeddings"
EMBED_FILE = os.path.join(EMBED_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_embeddings.npy")

# Make directory if missing
os.makedirs(EMBED_DIR, exist_ok=True)

def embed_chunks():
    # Check if chunk file exists
    if not os.path.exists(CHUNK_FILE):
        logging.error(f"Chunk file not found: {CHUNK_FILE}")
        return

    with open(CHUNK_FILE, "r", encoding="utf-8") as f:
        try:
            chunks = json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON: {e}")
            return

    # Clean up chunks
    valid_chunks = [chunk.strip() for chunk in chunks if isinstance(chunk, str) and chunk.strip()]
    if not valid_chunks:
        logging.warning("No valid chunks found for embedding.")
        return

    logging.info(f"Encoding {len(valid_chunks)} medical chunks...")
    embeddings = model.encode(valid_chunks, convert_to_numpy=True, show_progress_bar=True)

    np.save(EMBED_FILE, embeddings)
    logging.info(f"Saved embeddings to: {EMBED_FILE}")
    logging.info(f"Embeddings shape: {embeddings.shape}")

if __name__ == "__main__":
    embed_chunks()
