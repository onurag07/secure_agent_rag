import security
from langgraph.graph import StateGraph, START, END
from state import AgentState
from config import get_settings

settings = get_settings()


# NODE 1: prompt Gaurd (Security Layer 1)
def prompt_gaurd(state: AgentState)->dict:
    """Block dangerous Prompt before they reach to the LLM"""
    from security.prompt_guard import check_safety
    is_safe, thread = check_safety(state["query"])
    return {
        'is_safe':is_safe,
        'thread_type':thread
    }
    
# NODE 2: PII Redactor (Security Layer 2)
def pii_redact_node(state:AgentState)->dict:
    """remove personal info (names, phones, emails) from query"""
    from security.pii_redactor import redact
    clean = redact(state["query"])
    return {"sanitize_query":clean}

# NODE 3: Planner (breaks down complex questions)
def planner_node(state:AgentState)->dict:
    """ Understands intent and creates sub-questions """
    from agents.planner import plan
    intent, subs = plan(state['query'])
    return {
        "intent":intent,
        "sub_query":subs
    }

def retriever_node(state:AgentState)->dict:
    """retrieve document from the database"""
    from agents.retriever import search_db
    docs = search_db(state['sub_query'], [])
    return {"documents":docs}

def generator_node(state:AgentState)->dict:
    from agents.critic_generator import generate_response
    response = generate_response(state["sanitized_query"], state["retrieved_docs"], [])

def validator_node(state:AgentState)->dict:
    from security.output_validator import validate_output
    is_valid, reason = validate_output(state["draft_response"], state["intent"])
    if is_valid:
        return {"final_response":state["draft_response"]}
    else:
        return {
            "final_response":f"Response blocked by Output Validator : {reason}"
        }

def blocked_response(state:AgentState)->dict:
    return {
        "final_response":"Your response is bloacked by our security policy"
    }

def route_guard(state:AgentState)-> str:
    """direct node to next stage based on security level"""
    return "pii_redact" if state["is_safe"] else END

#  BUILD THE GRAPH

def build_graph():
    g = StateGraph(AgentState)
    # Add Node
    g.add_node("guard", prompt_gaurd)
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

    return g.compile()

app = build_graph()  # This is what main.py imports
