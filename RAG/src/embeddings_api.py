from fastapi import FastAPI
from pydantic import BaseModel
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import logging
import uvicorn
import threading

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Constants
CHUNKS_PATH = "./RAG/chunks/chunks.json"
EMBEDDINGS_PATH = "./RAG/embeddings/embeddings.npy"
MODEL_NAME = 'pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb'

# Load data once
logging.info("Loading chunks and embeddings...")
with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    chunks = json.load(f)
embeddings = np.load(EMBEDDINGS_PATH)

logging.info("Loading BioBERT model...")
model = SentenceTransformer(MODEL_NAME)

# FastAPI app
app = FastAPI(title="Medical Embedding Retrieval API")

class QueryRequest(BaseModel):
    query: str
    top_k: int = 2

def retrieve_similar_embeddings(query: str, top_k: int = 2):
    query_embedding = model.encode([query])
    similarities = cosine_similarity(query_embedding, embeddings)[0]
    top_k_indices = similarities.argsort()[-top_k:][::-1]

    results = []
    for idx in top_k_indices:
        results.append({
            "score": float(similarities[idx]),
            "chunk": chunks[idx],
            "index": int(idx)
        })

    return results

@app.post("/embeddapi")
def retrieve(request: QueryRequest):
    results = retrieve_similar_embeddings(request.query, request.top_k)
    return {"query": request.query, "results": results}

# Function for CLI input
def cli_input():
    while True:
        query = input("\n🧠 Enter your medical query (or 'exit' to quit): ")
        if query.lower() == "exit":
            print("👋 Exiting CLI input mode.")
            break
        results = retrieve_similar_embeddings(query, top_k=3)
        print("\n🔍 Top Matches:")
        for r in results:
            print(f"📄 Score: {r['score']:.4f} | Text: {r['chunk']}")
        print("-" * 80)

if __name__ == "__main__":
    # Start API in a separate thread
    threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8001, reload=False), daemon=True).start()

    # Run CLI input in main thread
    cli_input()


