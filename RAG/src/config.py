import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Settings
    HOST = "0.0.0.0"
    CHUNK_API_PORT = 8000
    EMBEDDINGS_API_PORT = 8001
    KNOWLEDGE_GRAPH_API_PORT = 8002
    
    # Model Settings
    EMBEDDING_MODEL = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
    EMBEDDING_DIM = 768
    
    # Vector Store Settings
    PINECONE_INDEX_NAME = "medical-rag-index"
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    
    # Neo4j Settings
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    
    # File Paths
    DATA_DIR = "./RAG/data"
    CHUNKS_FILE = "./RAG/chunks/chunks.json"
    EMBEDDINGS_FILE = "./RAG/embeddings/embeddings.npy"
    
    # Rate Limiting
    RATE_LIMIT = "5/minute"
    
    # Retrieval Settings
    DEFAULT_TOP_K = 3
    
    @classmethod
    def validate(cls):
        """Validate required environment variables"""
        required_vars = {
            "PINECONE_API_KEY": cls.PINECONE_API_KEY,
            "NEO4J_URI": cls.NEO4J_URI,
            "NEO4J_USERNAME": cls.NEO4J_USERNAME,
            "NEO4J_PASSWORD": cls.NEO4J_PASSWORD,
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}") 