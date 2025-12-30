from litellm import Router

model_list = [
    {
        "model_name": "deterministic",
        "litellm_params": {
            "model": "gpt-4o-mini",
            "temperature": 0.2,
        },
    },
    {
        "model_name": "deterministic",
        "litellm_params": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.2,
        },
    },
    {
        "model_name": "creative",
        "litellm_params": {
            "model": "gpt-4o-mini",
            "temperature": 0.7,
        },
    },
    {
        "model_name": "creative",
        "litellm_params": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.7,
        },
    },
]
LLM_ROUTER = Router(model_list=model_list)
