from litellm import Router

model_list = [
    {
        "model_name": "deterministic",
        "litellm_params": {
            "model": "gpt-4o-mini",
            "temperature": 0.2
        },
    },
    {
        "model_name": "deterministic_fallback",
        "litellm_params": {
            "model": "anthropic/claude-3-5-haiku-20241022",
            "temperature": 0.2
        },
    },
    {
        "model_name": "creative",
        "litellm_params": {
            "model": "gpt-4o-mini",
            "temperature": 0.7
        },
    },
    {
        "model_name": "creative_fallback",
        "litellm_params": {
            "model": "anthropic/claude-3-5-haiku-20241022",
            "temperature": 0.7
        },
    },
]
fallbacks = [
    {"deterministic": ["deterministic_fallback"]},
    {"creative": ["creative_fallback"]},
]

LLM_ROUTER = Router(
    model_list=model_list,
    fallbacks=fallbacks
)
