import os
from langsmith import Client

def bootstrap_langsmith():
    """Initializes LangSmith tracing if enabled."""
    if os.getenv("LANGCHAIN_TRACING_V2") == "true":
        client = Client()
        project_name = os.getenv("LANGCHAIN_PROJECT", "secure-agent-rag")
        print(f"✅ LangSmith Tracing Enabled. Project: {project_name}")
    else:
        print("⚠️ LangSmith Tracing Disabled.")

def create_eval_dataset_from_traces(project_name, dataset_name, filter_tags=None, limit=100):
    """Creates a dataset from production traces for evaluation."""
    client = Client()
    runs = client.list_runs(
        project_name=project_name,
        is_root=True,
        tags=filter_tags,
        limit=limit
    )
    dataset = client.create_dataset(dataset_name)
    for run in runs:
        client.create_example(
            inputs=run.inputs,
            outputs=run.outputs,
            dataset_id=dataset.id
        )
    return dataset.id