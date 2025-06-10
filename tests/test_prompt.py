import json
import random

from src.fwb.entity_extractor import EntityExtractor
from src.fwb.progress_buf import ProgressBuffer

# --- Configuration ---
# The book you want to test against.
BOOK_ID = "46029"

# A sample context to provide to the LLM.
# For a single-chapter test, this can be simple.
# You might want to experiment with providing a list of existing categories here.
CONTEXT_FOR_TESTING = ""


def main():
    """
    This script runs a single test to help fine-tune the entity extraction prompt.
    It does the following:
    1. Gets the total number of chapters for the specified book.
    2. Picks a random chapter.
    3. Fetches the text for that random chapter.
    4. Formats the full prompt that will be sent to the LLM.
    5. Calls the LLM and gets the raw output.
    6. Prints the full prompt and the raw output for easy evaluation.

    This script does NOT modify your progress.txt or save any entities,
    making it safe to run repeatedly for testing.
    """
    print("--- PROMPT TUNING SCRIPT ---")

    # --- 1. Setup ---
    # We use ProgressBuffer to get book info, but not to track progress.
    buffer = ProgressBuffer()
    extractor = EntityExtractor(book_id=BOOK_ID)

    # --- 2. Get a Random Chapter ---
    try:
        total_chapters = buffer.get_book_length(BOOK_ID)
        if not total_chapters:
            print(f"Error: Book '{BOOK_ID}' not found or has 0 chapters.")
            return

        random_chapter_num = random.randint(1, total_chapters)
        print(f"Book ID: {BOOK_ID}")
        print(f"Total Chapters: {total_chapters}")
        print(f"Testing with Random Chapter: {random_chapter_num}\n")

        chapter_text = buffer.get_source_chunk(BOOK_ID, random_chapter_num)
        if not chapter_text:
            print(f"Error: Could not retrieve text for chapter {random_chapter_num}.")
            return

    except Exception as e:
        print(f"An error occurred during setup: {e}")
        return

    # --- 3. Prepare and Display the Full Prompt ---
    # We manually format the prompt here to show exactly what the LLM will see.
    full_prompt = extractor.extract_prompt.format(
        context=CONTEXT_FOR_TESTING,
        text=chapter_text,
    )

    print("--- Full Prompt Sent to LLM ---")
    print(full_prompt)
    print("---------------------------------\n")

    # --- 4. Call the LLM and Get the Response ---
    print("--- LLM Raw JSON Output ---")
    try:
        # We call `extract_entities` directly to isolate the LLM call.
        # This avoids using/modifying the progress buffer.
        raw_json_output = extractor.extract_entities(
            context=CONTEXT_FOR_TESTING, text=chapter_text
        )

        # Print the raw output for inspection
        print(raw_json_output)

    except Exception as e:
        print(f"An error occurred while calling the LLM: {e}")

    print("\n--- End of Test ---")


if __name__ == "__main__":
    main()
