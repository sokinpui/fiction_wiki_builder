# llm_config.py
ORDERED_MODELS = [
    "gemini-2.5-pro-preview-03-25",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-2.0-flash-thinking-exp-01-21",
    "gemma-3-27b-it",
]

MODEL_RATE_LIMITS = {
    "gemini-2.5-pro-preview-03-25": {
        "rpm": 5,
        "rpd": 25,
        "tpm": 250000,
        "tpd": 1000000,
    },
    "gemini-2.5-flash-preview-05-20": {"rpm": 10, "rpd": 500, "tpm": 250000},
    "gemini-2.0-flash": {"rpm": 15, "rpd": 1500, "tpm": 1000000},
    "gemini-2.0-flash-lite": {"rpm": 30, "rpd": 1500, "tpm": 1000000},
    "gemini-1.5-flash": {"rpm": 15, "rpd": 500, "tpm": 250000},
    "gemini-2.0-flash-thinking-exp-01-21": {
        "rpm": 10,
        "rpd": 1000,
        "tpm": 500000,
    },
    "gemma-3-27b-it": {"rpm": 30, "rpd": 14400, "tpm": 15000},
    "default": {"rpm": 10, "rpd": 100, "tpm": 250000},
}
