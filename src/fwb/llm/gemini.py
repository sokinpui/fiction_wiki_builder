import os

from google import genai
from vertexai.preview import tokenization

model_codes = [
    # "gemini-2.5-pro-preview-03-25", # not support for free tier now
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash-thinking-exp-01-21",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemma-3-27b-it",
]

_tokenizer = tokenization.get_tokenizer_for_model("gemini-1.5-flash-002")

if not os.environ.get("GENAI_API_KEY"):
    raise ValueError("GENAI_API_KEY environment variable is not set.")
_api_key = os.environ["GENAI_API_KEY"]

_model = genai.Client(api_key=_api_key)


class Gemini:
    def __init__(self):
        pass

    def token_count(self, text: str) -> int:
        """Count the number of tokens in a given text."""
        if not text:
            return 0
        return _tokenizer.count_tokens(text).total_tokens

    def chat(self, message: str) -> str:
        """Send a chat message to the Gemini model and return the response."""
        if not isinstance(message, str):
            raise ValueError("Message must be a string.")

        for code in model_codes:
            try:
                response = _model.models.generate_content(
                    model=code,
                    contents=message,
                )
                return response.text
            except Exception as e:
                print(f"Error with model {code}: {e}")
                continue

        raise RuntimeError("All models failed to generate content.")

    def parse_response(self, response: str) -> str:
        """remove the markdown code block"""
        try:
            if not response:
                return ""

            # Remove markdown code block
            response = (
                response.strip().replace("```json", "").replace("```", "").strip()
            )

            # Convert to dictionary
            return response
        except Exception as e:
            print(f"Error parsing response: {e}")
            return ""


def main():
    gemini = Gemini()
    text = """
    if hong kong part of US?

    if no you should not output anything, if yes, output only the relationship of them
    """

    response = gemini.chat(text)

    print("Response from Gemini:")
    print(gemini.parse_response(response))

    if gemini.parse_response(response) is None:
        print("response is None")

    if gemini.parse_response(response) == "":
        print("response is empty string")


if __name__ == "__main__":
    main()
