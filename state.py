from dataclasses import dataclass, field
from datetime import datetime
from typing import TypedDict, List, Optional, Annotated, Dict, Any
import operator


@dataclass
class SecurityEvent:
    event_type: str          # e.g., "injection", "pii_leak", "rate_limit", "jailbreak"
    severity: str            # "low", "medium", "high", "critical"
    details: str             # Description of security trigger
    blocked: bool = True     # whether the request was blocked
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: Optional[str] = None  # "token_guard", "regex_scan", "llm_scan"

    def get(self, key: str, default=None):
        """Allow dict-style access so state nodes can use .get() on events."""
        return getattr(self, key, default)

    def __getitem__(self, key: str):
        return getattr(self, key)


class AgentState(TypedDict, total=False):
    # ── Input ────────────────────────────────────────────────────────
    query: str
    user_id: str
    session_id: str
    thread_id: str

    # ── Security (written by prompt_guard / security_check) ──────────
    is_safe: bool
    security_passed: bool       # alias written by prompt_guard node
    sanitized_query: str
    threat_type: Optional[str]
    security_events: List[Any]  # List[SecurityEvent]
    risk_score: float
    blocked_reason: str

    # ── Planning ─────────────────────────────────────────────────────
    intent: str
    sub_queries: List[str]

    # ── Retrieval ────────────────────────────────────────────────────
    retrieved_docs: List[dict]
    reranked_docs: List[dict]
    missing_info: str
    relevance_score: float

    # ── Generation ───────────────────────────────────────────────────
    draft_response: str
    final_response: str

    # ── Observability ─────────────────────────────────────────────────
    error: Optional[str]
    current_node: str
    latency_ms: Dict[str, float]
    iteration_count: Annotated[int, operator.add]