-- db/init.sql — auto-executed by Docker on first start

-- 1. Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Enable full-text search dictionary (for BM25-style hybrid search)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 3. Main documents table (replaces Qdrant collection)
CREATE TABLE IF NOT EXISTS rag_documents (
    id BIGSERIAL PRIMARY KEY,
    collection TEXT NOT NULL DEFAULT 'default',
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    embedding vector (384), -- 384 dims for BGE-small-en-v1.5
    content_tsv TSVECTOR GENERATED ALWAYS AS -- auto full-text search vector
    (
        to_tsvector ('english', content)
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW (),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW ()
);

-- 4. HNSW index for fast approximate nearest-neighbor search
--    m=16: max connections per node (higher = better recall, more memory)
--    ef_construction=64: search depth at index build time (higher = better quality)
CREATE INDEX IF NOT EXISTS rag_embedding_hnsw_idx ON rag_documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 5. GIN index for full-text search (hybrid search)
CREATE INDEX IF NOT EXISTS rag_fts_gin_idx ON rag_documents USING gin (content_tsv);

-- 6. JSONB index for metadata filtering
CREATE INDEX IF NOT EXISTS rag_metadata_gin_idx ON rag_documents USING gin (metadata);

-- 7. Collection + timestamp composite index
CREATE INDEX IF NOT EXISTS rag_collection_idx ON rag_documents (collection, created_at DESC);