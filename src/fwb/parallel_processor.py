# parallel_processor.py
import concurrent.futures
import logging

from .entity_extractor import (  # Use relative import if in the same package
    EntityExtractor,
)

# Configure logging if not already configured by entity_extractor.py
# (it's good practice for modules to get their own logger)
logger = logging.getLogger(__name__)
if (
    not logger.handlers
):  # Avoid adding multiple handlers if entity_extractor.py already set up root logger
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(threadName)s - %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class ParallelChapterProcessor:
    def __init__(self, book_id: str, max_threads: int = 10):
        """
        Initializes the ParallelChapterProcessor.

        Args:
            book_id: The ID of the book to process.
            max_threads: The maximum number of threads to use for processing.
        """
        if max_threads <= 0:
            raise ValueError("max_threads must be a positive integer.")
        self.book_id = book_id
        self.max_threads = max_threads
        # Each ParallelChapterProcessor instance will have its own EntityExtractor.
        # This is generally safer if EntityExtractor or its components (like Gemini client)
        # are not perfectly thread-safe or if you want to isolate resources per processor.
        # If EntityExtractor and Gemini() are fully thread-safe and lightweight to share,
        # you could consider passing an EntityExtractor instance instead.
        # For this setup, creating one per processor is fine.
        self.entity_extractor = EntityExtractor(book_id=self.book_id)
        logger.info(
            f"ParallelChapterProcessor initialized for book_id: {self.book_id} with max_threads: {self.max_threads}"
        )

    def process_all_chapters(self):
        """
        Processes all chapters of the book in parallel.
        """
        logger.info(
            f"Starting parallel processing for all chapters of book_id: {self.book_id}"
        )
        total_chapters = self.entity_extractor.get_book_length()

        if total_chapters == 0:
            logger.warning(
                f"No chapters found for book_id: {self.book_id}. Nothing to process."
            )
            return

        logger.info(
            f"Found {total_chapters} chapters for book_id: {self.book_id}. Distributing work to {self.max_threads} threads."
        )

        # Using ThreadPoolExecutor to manage a pool of threads
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_threads
        ) as executor:
            # Submit tasks for each chapter to the executor
            # The map function is a good way to apply a function to a sequence
            # and get results in order, but here we don't strictly need results back from process_chapter.
            # We primarily care about the side effect (inserting to ES).
            # Using executor.submit allows for more fine-grained control if needed,
            # and future.result() can be used to catch exceptions from worker threads.

            futures = []
            for chapter_id in range(1, total_chapters + 1):
                # The entity_extractor.process_chapter method will be called
                # with chapter_id as its argument in a separate thread.
                future = executor.submit(
                    self.entity_extractor.process_chapter, chapter_id
                )
                futures.append(future)

            # Wait for all submitted tasks to complete and handle any exceptions
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()  # Raises an exception if the task failed
                except Exception as e:
                    # process_chapter itself logs errors, but we can log that a task failed at this level too.
                    logger.error(
                        f"A chapter processing task for book_id {self.book_id} failed: {e}",
                        exc_info=True,
                    )

        logger.info(
            f"Parallel processing of all chapters for book_id: {self.book_id} completed."
        )

    def process_specific_chapters(self, chapter_ids: list[int]):
        """
        Processes a specific list of chapter IDs in parallel.

        Args:
            chapter_ids: A list of chapter integers to process.
        """
        if not chapter_ids:
            logger.warning("No chapter IDs provided for specific processing. Skipping.")
            return

        logger.info(
            f"Starting parallel processing for {len(chapter_ids)} specific chapters of book_id: {self.book_id}"
        )

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_threads
        ) as executor:
            futures = {
                executor.submit(
                    self.entity_extractor.process_chapter, chapter_id
                ): chapter_id
                for chapter_id in chapter_ids
            }

            for future in concurrent.futures.as_completed(futures):
                chapter_id = futures[future]
                try:
                    future.result()
                    logger.info(
                        f"Successfully processed chapter {chapter_id} for book {self.book_id}."
                    )
                except Exception as e:
                    logger.error(
                        f"Processing task for chapter {chapter_id} (book {self.book_id}) failed: {e}",
                        exc_info=True,
                    )
        logger.info(
            f"Parallel processing of specific chapters for book_id: {self.book_id} completed."
        )


# --- Example usage (can be in entity_extractor.py or a new main script) ---
# This would typically be in your main script or the if __name__ == "__main__": block
# of entity_extractor.py


def main_parallel_processing():
    book_id_to_process = "46029"  # Replace with a valid book_id from your Elasticsearch
    num_worker_threads = 10  # Up to 10, adjust as needed

    # Ensure Elasticsearch is running and the book index (e.g., book_46029) exists and has data.
    # Ensure ./prompt/entity_extraction.txt exists.
    # Ensure your llm.gemini module and Gemini class are correctly set up.

    processor = ParallelChapterProcessor(
        book_id=book_id_to_process, max_threads=num_worker_threads
    )
    processor.process_all_chapters()

    # Example for specific chapters:
    # chapters_to_process = [1, 3, 5]
    # processor.process_specific_chapters(chapters_to_process)


if __name__ == "__main__":
    # This allows running parallel_processor.py directly for testing
    # Make sure your PYTHONPATH is set up correctly if .entity_extractor is used,
    # or change the import to a direct one if files are in the same directory and not part of a package.
    # For example, if in the same dir: from entity_extractor import EntityExtractor

    # To run this directly and test, you might need to adjust imports
    # or run from a higher-level directory.
    # For simplicity, let's assume you'll call this main_parallel_processing
    # from your main script where entity_extractor.py is also imported.
    main_parallel_processing()
    # For direct testing, you might put main_parallel_processing() in entity_extractor.py's main
