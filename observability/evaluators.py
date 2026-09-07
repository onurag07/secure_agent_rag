from langsmith.evaluation import evaluate, LangChainStringEvaluator

def exact_match_evaluator(run, example):
    """Custom exact match evaluator (e.g., for PII/Security safety checks)."""
    expected = example.outputs.get("output", "")
    actual = run.outputs.get("output", "")
    return {"key": "exact_match", "score": int(expected == actual)}

def run_all_evaluators(dataset_name, experiment_prefix):
    """Runs all custom evaluators against a LangSmith dataset."""
    # Built-in LLM-as-a-judge evaluators
    qa_evaluator = LangChainStringEvaluator("qa")
    context_evaluator = LangChainStringEvaluator("context_qa")
    
    # Mock prediction function - replace with your LangGraph entry point
    # e.g., from main import app; return app.invoke(inputs)
    def predict(inputs):
        return {"output": "Mock pipeline response based on input"}

    # Execute the evaluation
    results = evaluate(
        predict,
        data=dataset_name,
        evaluators=[qa_evaluator, context_evaluator, exact_match_evaluator],
        experiment_prefix=experiment_prefix,
    )
    return results