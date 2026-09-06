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
    #Input
    query: str
    user_id:str
    session_id:str
    
    #security
    is_safe:bool
    sanitized_query:str
    thread_type:Optional[str]
    security_events:List[SecurityEvent]

    #planning
    intentd:str
    sub_queries:List[str]

    #Retrieval
    retrieved_docs:List[str]
    reranked_docs:List[str]

    #Generattion
    draft_response:str
    final_response:str
    
    #Metadata
    error:Optional[str]
    iteration_count:Annotated[int,operator.add]
