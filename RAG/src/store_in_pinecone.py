import os
import json
import numpy as np
import logging
import hashlib
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from time import time

# Load .env variables
load_dotenv()

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# Constants
INDEX_NAME = "medical-rag-index"
EMBEDDING_DIM = 768
CHUNKS_FILE = "./RAG/chunks/20250804_132718_chunks.json"
EMBEDDINGS_FILE = "./RAG/embeddings/20250804_133829_embeddings.npy"

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_names = pc.list_indexes().names()

if INDEX_NAME not in index_names:
    logging.info(f"🆕 Creating Pinecone index: {INDEX_NAME}")
    pc.create_index(
        name=INDEX_NAME,
        dimension=EMBEDDING_DIM,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

index = pc.Index(INDEX_NAME)

# Generate unique ID based on content hash
def generate_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# Batch upsert to Pinecone
def batch_upsert(vectors, batch_size=100):
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        try:
            index.upsert(vectors=batch)
            logging.info(f"📤 Upserted batch {i}–{i + len(batch)}")
        except Exception as e:
            logging.error(f"❌ Failed batch {i}–{i + len(batch)}: {e}")

# Main function
def upsert_to_pinecone():
    try:
        with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        embeddings = np.load(EMBEDDINGS_FILE)

        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings")

        vectors = [
            (generate_id(chunks[i]), embeddings[i].tolist(), {"text": chunks[i]})
            for i in range(len(chunks))
        ]

        logging.info(f"🔢 Preparing to upsert {len(vectors)} vectors to Pinecone...")
        start = time()
        batch_upsert(vectors)
        logging.info(f"✅ All vectors upserted in {round(time() - start, 2)}s")

        # Optional: Log index stats
        stats = index.describe_index_stats()
        logging.info(f"📦 Total vectors in Pinecone: {stats['total_vector_count']}")

    except Exception as e:
        logging.error(f"❌ Error during upsert: {str(e)}")

if __name__ == "__main__":
    upsert_to_pinecone()
