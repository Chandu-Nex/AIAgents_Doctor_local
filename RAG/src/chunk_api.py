from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import logging
import os
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
import warnings
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

# Validate required environment variables
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY environment variable is required")

# Logging setup
os.makedirs("logs", exist_ok=True)
warnings.filterwarnings(
    "ignore",
    message="`encoder_attention_mask` is deprecated",
    category=FutureWarning,
    module="torch"
)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("logs/app.log"), logging.StreamHandler()]
)
feedback_logger = logging.getLogger("feedback")
feedback_handler = logging.FileHandler("logs/feedback.log")
feedback_logger.addHandler(feedback_handler)
feedback_logger.setLevel(logging.INFO)

# FastAPI app
app = FastAPI(title="Medical RAG API")

# CORS configuration
origins = [
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Embedding model
model_name = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
embedder = HuggingFaceEmbeddings(model_name=model_name)

# Pinecone setup
os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY
index_name = "medical-rag-index"

try:
    vectorstore = PineconeVectorStore(index_name=index_name, embedding=embedder)
except Exception as e:
    logging.error(f"Failed to initialize Pinecone vectorstore: {e}")
    raise

# Request models
class Query(BaseModel):
    text: str

class Feedback(BaseModel):
    query: str
    response: str
    rating: int
    comment: str = None

# Vector retrieval
def retrieve_from_vector(query: str, k: int = 3):
    try:
        results = vectorstore.similarity_search(query, k=k)
        return results or []
    except Exception as e:
        logging.error(f"Retrieval error: {str(e)}")
        return []

def rag_query(query):
    results = retrieve_from_vector(query)
    if not results:
        return "No relevant information found in database."
    return "\n".join([res.page_content for res in results])

# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "ok"}

# Main POST query API
@app.post("/chunkapi")
@limiter.limit("5/minute")
async def handle_query(request: Request, q: Query):
    try:
        response_text = rag_query(q.text)

        def stream_response():
            yield response_text

        logging.info(f"Processed query: {q.text}")
        return StreamingResponse(stream_response(), media_type="text/plain")

    except Exception as e:
        logging.error(f"API error: {str(e)}")
        return {"error": str(e), "response": "Unable to process query."}

# Feedback API
@app.post("/feedback")
async def receive_feedback(fb: Feedback):
    feedback_logger.info(
        f"Feedback received: Query='{fb.query}', Response='{fb.response}', "
        f"Rating={fb.rating}, Comment='{fb.comment}'"
    )
    return {"status": "feedback logged"}

# Run the API when executed directly
if __name__ == "__main__":
    uvicorn.run("chunk_api:app", host="0.0.0.0", port=8000, reload=False)
