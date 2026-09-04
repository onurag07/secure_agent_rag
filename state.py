from typing import TypedDict, List, Optional, Annotated
import operator

class AgentState(TypedDict):
    #Input
    query: str
    user_id:str
    session_id:str
    
    #security
    is_safe:bool
    sanitized_query:str
    thread_type:Optional[str]
    #planning
    intentd:str
    sub_query:List[str]
    #Retrieval
    retrieved_docs:List[str]
    reranked_docs:List[str]
    #Generattion
    draft_response:str
    final_response:str
    #Metadata
    error:Optional[str]
    iteration_count:Annotated[int,operator.add]
