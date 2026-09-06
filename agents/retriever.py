from langchain_community.vectorstores import Chroma 
from langchain_hugging import HuggingFaceEmbeddings

#initiallize embedding model and vector database

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_store = Chroma(
    collection_name="rag_documents",
    embedding_function=embeddings,
    persist_directory="./chroma_data",
)

#seed the database if empty
if vector_store.collection.count() == 0:
    vector_store.add_texts(
        texts=[
            "RAG (Retrieval-Augmented Generation) connect LLMs to external data.",
            "Security in LLMs involves input guardrails and output validation.",
            "LangGraph is an orchestration framework for AI agents."
        ]
    )

def retrieve_docs(sub_queries: list[str]) -> list[dict]:
    """
    Performs real vector similarity search using Chroma DB and returns documents.
    """
    all_docs = []
    for query in sub_queries:
        # retrieve top 2 most similar documents for each sub-query
        results = vector_store.similarity_search_with_score(query, k=2)
        for doc, score in results:
            all_docs.append({"content": doc.page_content, "score": score})

    # deduplicate and sort by score
    unique_docs = {doc["content"]: doc for doc in all_docs}.values()
    return sorted(unique_docs, key=lambda x: x["score"], reverse=True)
    