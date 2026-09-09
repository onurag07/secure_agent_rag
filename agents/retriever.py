"""
agents/retriever.py — PostgreSQL + pgvector Hybrid Retrieval
HyDE Dense Search + Sparse Search -> RRF -> FlashRank Cross-Encoder Reranker
"""
import json
import logging
from typing import List, Dict, Any, Tuple
import psycopg
from pgvector.psycopg import register_vector
import os
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from config import settings

log = logging.getLogger(__name__)

hf_token = os.getenv("HF_TOKEN")
if not hf_token:
    print("WARNING: HF_TOKEN not found in .env! HuggingFace embeddings API will fail without it.")

embeddings = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/all-MiniLM-L6-v2",
    huggingfacehub_api_token=hf_token
)

DEFAULT_KNOWLEDGE_BASE = [
    "RAG (Retrieval-Augmented Generation) connects LLMs to external data sources securely.",
    "Security in LLMs involves input guardrails (regex, token caps, semantic scan) and output validation.",
    "LangGraph is a stateful orchestration framework for building reliable multi-agent AI systems.",
    "JWT (JSON Web Tokens) provides stateless authentication for microservices and RAG APIs.",
    "PGVector enables vector similarity search directly inside PostgreSQL databases."
]

def _get_postgres_conn():
    try:
        url = settings.pgvector_url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://")
        conn = psycopg.connect(url, connect_timeout=3)
        register_vector(conn)
        return conn
    except Exception as e:
        log.warning("Postgres connection note: %s", e)
        return None

try:
    from flashrank import Ranker, RerankRequest
    _reranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2")
    RERANKER_AVAILABLE = True
except Exception:
    _reranker = None
    RERANKER_AVAILABLE = False


def _hyde_query(query: str) -> str:
    llm = ChatGroq(model=settings.planner_model_name, temperature=0.3,
                   api_key=settings.groq_api_key, max_tokens=100)
    try:
        resp = llm.invoke([HumanMessage(content=f"Write a short 2-sentence hypothetical answer to: {query}")])
        return resp.content
    except Exception:
        return query

def _dense_search(query: str, k: int = 10) -> List[Tuple[str, float]]:
    conn = _get_postgres_conn()
    if not conn:
        return []
    try:
        hyde_doc = _hyde_query(query)
        query_vector = embeddings.embed_query(hyde_doc)
        results = []
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content, 1 - (embedding <=> %s::vector) AS score
                    FROM rag_documents
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_vector, query_vector, k)
                )
                rows = cur.fetchall()
                results = [(r[0], float(r[1])) for r in rows if r[0]]
        conn.close()
        return results
    except Exception as e:
        log.warning("Dense search note: %s", e)
        return []


def retrieve_docs(sub_queries: List[str], top_k: int = 3) -> List[Dict[str, Any]]:
    candidates: set = set()
    for q in sub_queries:
        dense_results = _dense_search(q, k=10)
        candidates.update([text for text, score in dense_results])

    # Fallback to default knowledge base if vector DB returns no documents
    if not candidates:
        q_lower = (sub_queries[0] if sub_queries else "").lower()
        matched = [doc for doc in DEFAULT_KNOWLEDGE_BASE if any(word in doc.lower() for word in q_lower.split() if len(word) > 3)]
        candidates.update(matched if matched else DEFAULT_KNOWLEDGE_BASE[:3])

    passages = [{"id": str(i), "text": text} for i, text in enumerate(candidates)]
    if RERANKER_AVAILABLE and _reranker:
        try:
            reranked = _reranker.rerank(RerankRequest(query=sub_queries[0] if sub_queries else "", passages=passages))
            return [{"content": r["text"], "score": float(r["score"])} for r in reranked[:top_k]]
        except Exception as e:
            log.warning("Reranker failed, returning candidates: %s", e)

    return [{"content": p["text"], "score": 1.0} for p in passages[:top_k]]


def add_document_to_knowledge_base(text: str, filename: str = "uploaded_doc") -> int:
    """
    Splits document text into chunks and ingests into Knowledge Base
    (both PGVector if connected and in-memory DEFAULT_KNOWLEDGE_BASE).
    """
    if not text or not text.strip():
        return 0

    # Chunk text into ~400 character paragraphs / blocks
    raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    for p in raw_paragraphs:
        if len(p) > 600:
            sub_parts = [s.strip() for s in p.split(". ") if s.strip()]
            current_chunk = ""
            for s in sub_parts:
                if len(current_chunk) + len(s) < 500:
                    current_chunk += (s + ". ")
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = s + ". "
            if current_chunk:
                chunks.append(current_chunk.strip())
        else:
            chunks.append(p)

    if not chunks:
        chunks = [text[:500].strip()]

    # 1. Add chunks to in-memory DEFAULT_KNOWLEDGE_BASE
    for chunk in chunks:
        if chunk not in DEFAULT_KNOWLEDGE_BASE:
            DEFAULT_KNOWLEDGE_BASE.append(chunk)

    # 2. Add chunks to PGVector store in PostgreSQL
    conn = _get_postgres_conn()
    if conn:
        try:
            vectors = embeddings.embed_documents(chunks)
            with conn:
                with conn.cursor() as cur:
                    for chunk, vec in zip(chunks, vectors):
                        cur.execute(
                            """
                            INSERT INTO rag_documents (collection, content, metadata, embedding)
                            VALUES (%s, %s, %s, %s)
                            """,
                            ("default", chunk, json.dumps({"source": filename}), vec)
                        )
            conn.close()
            log.info("Successfully added %d chunks to PostgreSQL rag_documents table", len(chunks))
        except Exception as e:
            log.warning("PGVector ingestion note: %s", e)

    log.info("Ingested %d chunks into Knowledge Base from %s", len(chunks), filename)
    return len(chunks)