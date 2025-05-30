# gemini_model.py
import logging
import os
from typing import Dict, Optional, Type, Union

import google.generativeai as genai
from google.generativeai import types as genai_types
from pydantic import BaseModel

from .google_helper import llm_config
from .google_helper.google_tool_utils import pydantic_to_google_tool
from .google_helper.rate_tracker import ModelRateTracker

try:
    from vertexai.preview import tokenization

    VERTEX_TOKENIZER_AVAILABLE = True
except ImportError:
    VERTEX_TOKENIZER_AVAILABLE = False
    print(
        "Warning: vertexai.preview.tokenization not found. Local token counting may be less accurate or disabled."
    )


class Gemini:
    def __init__(self, api_key: Optional[str] = None):
        # Get a logger instance. Naming it after the class is a common convention.
        self._logger = logging.getLogger(f"{__name__}.GeminiLLMHandler")

        # Configure basic logging if no handlers are configured for the root logger.
        # This ensures that logs are visible by default if the calling application
        # hasn't set up its own logging.
        if not logging.getLogger().hasHandlers():
            logging.basicConfig(
                level=logging.INFO,  # Default level
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
            self._logger.info("Basic logging configured by GeminiLLMHandler.")

        self.genai_api_key = api_key or os.environ.get("GENAI_API_KEY")

        if not self.genai_api_key:
            self._logger.error("GENAI_API_KEY environment variable not set.")
            raise ValueError("GENAI_API_KEY environment variable not set.")

        genai.configure(api_key=self.genai_api_key)
        # os.environ["GOOGLE_API_KEY"] = self.genai_api_key # genai.configure should handle this

        self.ordered_model_names = llm_config.ORDERED_MODELS
        self.rate_tracker = ModelRateTracker()  # No logger argument needed now
        self.rate_tracker.set_model_configs(llm_config.MODEL_RATE_LIMITS)

        self._active_genai_models: Dict[str, genai.GenerativeModel] = {}

        self._logger.info(
            f"GeminiLLMHandler initialized. Model preference: {', '.join(self.ordered_model_names)}"
        )
        if not VERTEX_TOKENIZER_AVAILABLE:
            self._logger.warning(
                "vertexai.preview.tokenization not available. Token counting will rely on genai API or basic estimation."
            )

    def _get_genai_model_instance(self, model_name: str) -> genai.GenerativeModel:
        if model_name not in self._active_genai_models:
            try:
                generation_config = genai.GenerationConfig(temperature=0.7)
                safety_settings = {}  # Configure as needed

                instance = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                )
                self._active_genai_models[model_name] = instance
                self._logger.info(
                    f"Initialized genai.GenerativeModel for: {model_name}"
                )
            except Exception as e:
                self._logger.error(
                    f"Failed to initialize genai.GenerativeModel for {model_name}: {e}",
                    exc_info=True,
                )
                raise
        return self._active_genai_models[model_name]

    def token_count(
        self,
        text: Optional[str],
        model_name_for_tokenizer: str = "gemini-1.5-flash-latest",
    ) -> int:
        if not text:
            return 0

        current_model_name_for_log = model_name_for_tokenizer  # For logging clarity

        if VERTEX_TOKENIZER_AVAILABLE:
            try:
                base_model_name = model_name_for_tokenizer.split("/")[-1]
                # Check if model name is known to be problematic or needs adjustment for vertex tokenizer
                if "preview" in base_model_name or "experimental" in base_model_name:
                    # Vertex tokenizer might prefer more stable versions or base names
                    # E.g., "gemini-1.5-flash" instead of "gemini-1.5-flash-preview-xxxx"
                    # This part is heuristic and might need adjustment based on vertexai library behavior
                    parts = base_model_name.split("-")
                    if len(parts) > 2 and any(
                        kw in parts[-1] for kw in ["preview", "experimental", "latest"]
                    ):
                        potential_base = "-".join(
                            parts[:-1]
                        )  # e.g., "gemini-1.5-flash"
                        # Test this simpler name if it's different
                        try:
                            tokenizer_test = tokenization.get_tokenizer_for_model(
                                potential_base
                            )
                            base_model_name = (
                                potential_base  # Use simpler name if it works
                            )
                            current_model_name_for_log = base_model_name
                            self._logger.debug(
                                f"Using simplified model name '{base_model_name}' for Vertex tokenizer."
                            )
                        except Exception:
                            self._logger.debug(
                                f"Simplified Vertex tokenizer name '{potential_base}' failed, using original '{base_model_name}'."
                            )

                tokenizer = tokenization.get_tokenizer_for_model(base_model_name)
                count_response = tokenizer.count_tokens(text)
                self._logger.debug(
                    f"Token count (Vertex) for '{current_model_name_for_log}': {count_response.total_tokens}"
                )
                return count_response.total_tokens
            except Exception as e_vertex:
                self._logger.warning(
                    f"Local token count (Vertex) for '{current_model_name_for_log}' failed: {e_vertex}. Falling back."
                )

        try:
            # Ensure model_name_for_tokenizer is appropriate for genai.count_tokens
            # Usually, the direct model names (e.g., "gemini-1.5-flash-latest") work,
            # but sometimes it might need "models/gemini-1.5-flash-latest"
            api_model_name = model_name_for_tokenizer
            if not api_model_name.startswith("models/") and (
                "embedding" in api_model_name
            ):  # Prefix for known embedding models
                api_model_name = f"models/{api_model_name}"

            if "embedding" in api_model_name.lower():
                # genai.count_tokens might not support embedding models or might have different behavior
                # For general text, switch to a known generative model for counting
                fallback_gen_model = "gemini-1.0-pro"  # or gemini-1.5-flash-latest
                self._logger.debug(
                    f"Switched from embedding model '{api_model_name}' to '{fallback_gen_model}' for genai.count_tokens."
                )
                api_model_name = fallback_gen_model

            response = genai.count_tokens(
                model=api_model_name, contents=[text]
            )  # contents should be a list
            self._logger.debug(
                f"Token count (genai API) for '{api_model_name}': {response.total_tokens}"
            )
            return response.total_tokens
        except Exception as e_genai:
            self._logger.warning(
                f"API token count (genai API) for '{api_model_name}' failed: {e_genai}. Basic estimate."
            )

        count = len(text.split())
        self._logger.debug(f"Token count (basic split) for text: {count}")
        return count

    def generate(
        self, prompt: str, schema: Optional[Type[BaseModel]] = None
    ) -> Union[str, BaseModel, None]:
        tools = None
        tool_config_dict = None

        if schema:
            try:
                google_tool = pydantic_to_google_tool(schema)
                tools = [google_tool]
                tool_config_dict = {"function_calling_config": {"mode": "ANY"}}
                self._logger.debug(
                    f"Attempting structured output: {schema.__name__} (Tool: {google_tool.function_declarations[0].name})"
                )
            except Exception as e:
                self._logger.error(
                    f"Pydantic to Google Tool conversion error: {e}", exc_info=True
                )
                self._logger.warning(
                    "Proceeding with standard text generation (schema ignored)."
                )
                schema = None  # Clear schema if conversion failed

        last_error: Optional[Exception] = None

        for model_name in self.ordered_model_names:
            is_limited, reason = self.rate_tracker.is_rate_limited(model_name)
            if is_limited:
                wait_time = self.rate_tracker.get_wait_time(model_name)
                self._logger.warning(
                    f"Model {model_name} rate-limited ({reason}). Est. wait: {wait_time:.2f}s. Trying next model."
                )
                last_error = Exception(f"Rate limited on {model_name} ({reason})")
                continue

            try:
                self._logger.info(f"Attempting generation with model: {model_name}")
                model_instance = self._get_genai_model_instance(model_name)

                response = model_instance.generate_content(
                    prompt, tools=tools, tool_config=tool_config_dict
                )
                self.rate_tracker.record_request(model_name)

                if (
                    schema
                    and response.candidates
                    and response.candidates[0].content.parts
                ):
                    fc_part = next(
                        (
                            p.function_call
                            for p in response.candidates[0].content.parts
                            if p.function_call
                        ),
                        None,
                    )

                    if fc_part:
                        fc_name = fc_part.name
                        fc_args = dict(fc_part.args)
                        self._logger.debug(
                            f"Model {model_name} returned function call '{fc_name}' with args: {fc_args}"
                        )

                        if fc_name != schema.__name__:
                            self._logger.warning(
                                f"Expected tool '{schema.__name__}', got '{fc_name}'. Validating anyway."
                            )

                        try:
                            validated_data = schema.model_validate(fc_args)
                            self._logger.info(
                                f"Structured output from {model_name} validated with {schema.__name__}."
                            )
                            return validated_data
                        except Exception as val_err:
                            self._logger.error(
                                f"Pydantic validation failed for {schema.__name__} (data from {model_name}): {val_err}",
                                exc_info=True,
                            )
                            last_error = val_err
                            continue
                    else:
                        self._logger.warning(
                            f"Schema {schema.__name__} provided, but no function call from {model_name}. Parts: {[str(p) for p in response.parts]}"
                        )
                        last_error = Exception(
                            f"No function call from {model_name} for {schema.__name__}"
                        )
                        # If text content is present, consider returning it as a fallback? Or always require tool for schema?
                        # For now, if schema is set, we expect a tool call.
                        if response.text:  # Check if there's text content
                            self._logger.info(
                                f"Model {model_name} provided text instead of function call: '{response.text[:100]}...'"
                            )
                        continue

                try:  # For non-schema or if schema processing didn't return
                    text_content = response.text
                    self._logger.info(f"Text response from {model_name} received.")
                    return text_content
                except (
                    ValueError
                ):  # response.text can raise ValueError if content is blocked
                    self._logger.warning(
                        f"Response from {model_name} blocked or no text (ValueError). Parts: {[str(p) for p in response.parts]}"
                    )
                    last_error = ValueError(f"Blocked/empty response from {model_name}")
                    continue
                except Exception as text_err:
                    self._logger.error(
                        f"Error extracting text from {model_name} response: {text_err}",
                        exc_info=True,
                    )
                    last_error = text_err
                    continue

            except genai_types.BlockedPromptException as bpe:
                self._logger.warning(f"Prompt blocked for model {model_name}: {bpe}")
                last_error = bpe
                continue
            except (
                genai_types.StopCandidateException
            ) as sce:  # candidate.finish_reason ==อื่น ๆ
                self._logger.warning(
                    f"Candidate generation stopped for {model_name}: {sce.args}"
                )
                last_error = sce
                continue
            except Exception as e:
                self._logger.error(
                    f"API call to {model_name} failed: {e}", exc_info=True
                )
                last_error = e
                continue

        self._logger.error(
            "All models failed or were rate-limited. No response generated."
        )
        if last_error:
            self._logger.error(
                f"Last error: {last_error}", exc_info=isinstance(last_error, Exception)
            )
        return None
