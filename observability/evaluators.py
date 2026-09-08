from langsmith.evaluation import evaluate
# Note: LangChainStringEvaluator was removed from newer langsmith SDK
# versions (0.2+). Write evaluators as plain functions instead.

def exact_match_evaluator(run, example):
    """Custom exact match evaluator (e.g., for PII/Security safety checks)."""
    expected = example.outputs.get("output", "")
    actual = run.outputs.get("output", "")
    return {"key": "exact_match", "score": int(expected == actual)}

def run_all_evaluators(dataset_name, experiment_prefix):
    """Runs all custom evaluators against a LangSmith dataset."""
    import asyncio
    from graph import app as agent_graph

    def predict(inputs):
        # Real entry point — same graph main.py's /api/chat calls, run synchronously here
        # since LangSmith's evaluate() expects a plain sync function.
        state = {"query": inputs["query"], "user_id": "eval", "session_id": "eval",
                  "thread_id": "eval", "security_events": [], "iteration_count": 0}
        config = {"configurable": {"thread_id": "eval", "session_id": "eval"}}
        result = asyncio.run(agent_graph.ainvoke(state, config=config))
        return {"output": result.get("final_response", "")}

    # Execute the evaluation
    results = evaluate(
        predict,
        data=dataset_name,
        evaluators=[exact_match_evaluator],
        experiment_prefix=experiment_prefix,
    )
    return results