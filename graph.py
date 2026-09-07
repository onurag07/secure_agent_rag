from langgraph.graph import StateGraph, START, END
from state import AgentState
from config import settings
from langgraph.checkpoint.memory import MemorySaver

# --- Nodes ---
def prompt_guard(state: AgentState) -> dict:
    from security.prompt_guard import check_safety
    is_safe, threat, events = check_safety(state.get("query", ""))
    current_events = state.get("security_events", [])
    return {"is_safe": is_safe, "threat_type": threat, "security_events": current_events + events}

def pii_redact_node(state: AgentState) -> dict:
    from security.pii_redactor import redact
    clean = redact(state.get("query", ""))
    return {"sanitized_query": clean}

def planner_node(state: AgentState) -> dict:
    from agents.planner import plan
    intent, subs = plan(state.get("sanitized_query", ""))
    return {"intent": intent, "sub_queries": subs}

def retriever_node(state: AgentState) -> dict:
    from agents.retriever import retrieve_docs
    docs = retrieve_docs(state.get("sub_queries", []))
    return {"retrieved_docs": docs}

def generator_node(state: AgentState) -> dict:
    from agents.critic_generator import generate_response
    resp = generate_response(state.get("sanitized_query", ""), state.get("retrieved_docs", []))
    return {"draft_response": resp}

def validator_node(state: AgentState) -> dict:
    from security.output_validator import validate_output
    is_valid, reason = validate_output(state.get("draft_response", ""))
    if is_valid:
        return {"final_response": state.get("draft_response")}
    else:
        return {"final_response": f"Response blocked by Output Validator: {reason}"}

def blocked_response(state: AgentState) -> dict:
    return {"final_response": "Your request was blocked by our security policy."}

# --- Conditional Edges ---
def route_guard(state: AgentState) -> str:
    return "pii_redact" if state.get("is_safe", False) else "blocked_response"

# --- Build Graph ---
def build_graph():
    memory = MemorySaver()
    g = StateGraph(AgentState)
    
    g.add_node("guard", prompt_guard)
    g.add_node("pii_redact", pii_redact_node)
    g.add_node("planner", planner_node)
    g.add_node("retriever", retriever_node)
    g.add_node("generator", generator_node)
    g.add_node("validator", validator_node)
    g.add_node("blocked_response", blocked_response)

    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", route_guard)
    g.add_edge("pii_redact", "planner")
    g.add_edge("planner", "retriever")
    g.add_edge("retriever", "generator")
    g.add_edge("generator", "validator")
    g.add_edge("validator", END)
    g.add_edge("blocked_response", END)

    return g.compile(checkpointer=memory)

app = build_graph()