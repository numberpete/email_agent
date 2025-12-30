from litellm import Router

model_list = [
    {
        "model_name": "deterministic",
        "litellm_params": {
            "model": "openai/gpt-4o-mini",
            "temperature": 0.2
        },
    },
    {
        "model_name": "deterministic_fallback",
        "litellm_params": {
            "model": "gemini/gemini-2.0-flash",
            "temperature": 0.3
        },
    },
    {
        "model_name": "creative",
        "litellm_params": {
            "model": "openai/gpt-4o-mini",
            "temperature": 0.7
        },
    },
    {
        "model_name": "creative_fallback",
        "litellm_params": {
            "model": "gemini/gemini-2.0-flash",
            "temperature": 1.2
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
