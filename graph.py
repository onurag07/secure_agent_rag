from langgraph.graph import StateGraph, START, END
from state import AgentState
from config import settings
from langgraph.checkpoint.memory import MemorySaver

def prompt_guard(state: AgentState) -> dict:
    from security.prompt_guard import security_check
    result = security_check(state)
    return {
        "is_safe": result.get("security_passed", False),
        "threat_type": result.get("security_events", [{}])[0].get("event_type", "none") if result.get("security_events") else "none",
        "security_events": result.get("security_events", []),
        "risk_score": result.get("risk_score", 0.0),
    }

def pii_redact_node(state: AgentState) -> dict:
    from security.pii_redactor import redact
    return {"sanitized_query": redact(state.get("query", ""))}

def planner_node(state: AgentState) -> dict:
    from agents.planner import plan
    intent, subs = plan(state.get("sanitized_query", ""))
    return {"intent": intent, "sub_queries": subs}

def retriever_node(state: AgentState) -> dict:
    from agents.retriever import retrieve_docs
    docs = retrieve_docs(state.get("sub_queries", []))
    return {"retrieved_docs": docs}

def critic_node(state: AgentState) -> dict:
    from agents.critic_generator import critic_agent
    res = critic_agent(state.get("sanitized_query", ""), state.get("retrieved_docs", []))
    return {"relevance_score": res.get("relevance", 1.0), "missing_info": res.get("missing", "")}

def rewriter_node(state: AgentState) -> dict:
    from agents.critic_generator import rewriter_agent
    new_subs = rewriter_agent(state.get("sanitized_query", ""), state.get("missing_info", ""))
    return {"sub_queries": new_subs, "iteration_count": state.get("iteration_count", 0) + 1}

def generator_node(state: AgentState) -> dict:
    from agents.critic_generator import generate_response
    resp = generate_response(state.get("sanitized_query", ""), state.get("retrieved_docs", []))
    return {"draft_response": resp}

def validator_node(state: AgentState) -> dict:
    from security.output_validator import validate_output
    is_valid, reason = validate_output(state.get("draft_response", ""), state.get("retrieved_docs", []))
    if is_valid:
        return {"final_response": state.get("draft_response")}
    return {"final_response": f"Response blocked by Output Validator: {reason}"}

def blocked_response(state: AgentState) -> dict:
    return {"final_response": "Your request was blocked by security policy."}

def route_guard(state: AgentState) -> str:
    return "pii_redact" if state.get("is_safe", False) else "blocked_response"

def route_critic(state: AgentState) -> str:
    # Token Strategy 6: Cap retry loop to max 3 iterations
    if state.get("relevance_score", 1.0) < 0.6 and state.get("iteration_count", 0) < 3:
        return "rewriter"
    return "generator"

def build_graph():
    memory = MemorySaver()  # Caching Layer 4: LangGraph Stateful Checkpointer
    g = StateGraph(AgentState)

    g.add_node("guard", prompt_guard)
    g.add_node("pii_redact", pii_redact_node)
    g.add_node("planner", planner_node)
    g.add_node("retriever", retriever_node)
    g.add_node("critic", critic_node)
    g.add_node("rewriter", rewriter_node)
    g.add_node("generator", generator_node)
    g.add_node("validator", validator_node)
    g.add_node("blocked_response", blocked_response)

    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", route_guard)
    g.add_edge("pii_redact", "planner")
    g.add_edge("planner", "retriever")
    g.add_edge("retriever", "critic")
    g.add_conditional_edges("critic", route_critic)
    g.add_edge("rewriter", "retriever")
    g.add_edge("generator", "validator")
    g.add_edge("validator", END)
    g.add_edge("blocked_response", END)

    return g.compile(checkpointer=memory)

app = build_graph()