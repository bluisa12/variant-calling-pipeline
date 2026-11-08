"""Optional AI steps for the variant calling pipeline.

Everything here is opt-in: the core pipeline never imports this package, so it
runs (and reproduces its results) without an API key.

Modules:
    config  - reads AI settings from config.yaml and the API key from the environment
    client  - the only module that talks to the LLM provider (FreeLLMAPI)
"""

from .config import AISettings, MissingAPIKeyError, load_api_key

__all__ = ["AISettings", "MissingAPIKeyError", "load_api_key"]
