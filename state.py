from dataclasses import dataclass, field
from datetime import datetime
from typing import TypedDict, List, Optional, Annotated
import operator

@dataclass
class SecurityEvent:
    event_type:str                                                          # e.g., "injection", "pii_leak", "rate_limit", "jailbreak"
    severity:str                                                            # "low", "medium", "high", "critical"
    details:str                                                             # Description of security trigger
    blocked:bool = True                                                     # whether the request was blocked
    timestamp: datetime = field(default_factory=datetime.utcnow)            # Time of event
    source:Optional[str] = None                                             # Source of the event (e.g., "token_guard", "regex_scan", "llm_scan") 
    
class AgentState(TypedDict):
    # Input
    query: str
    user_id: str
    session_id: str
    thread_id: str
    
    # Security
    is_safe: bool
    sanitized_query: str
    threat_type: Optional[str]
    security_events: List[SecurityEvent]
    
    # Planning
    intent: str
    sub_queries: List[str]
    
    # Retrieval
    retrieved_docs: List[dict]
    reranked_docs: List[dict]
    
    # Generation
    draft_response: str
    final_response: str
    
    # Metadata
    error: Optional[str]
    iteration_count: Annotated[int, operator.add]


# Agent communication example:
def critic_agent(state: AgentState) -> AgentState:
    # Reads from retrieval agent's output
    docs  = state["retrieved_docs"]      # ← retriever wrote this
    query = state["sanitized_query"]     # ← pii_redact wrote this

    score = evaluate_relevance(docs, query)

    # Writes for generator agent to read
    return {**state, "retrieval_score": score}  # → generator will read this