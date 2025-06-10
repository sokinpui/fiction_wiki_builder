# fwb/file_store.py
# This version stores all data for a book (progress and entities)
# in a dedicated subdirectory within the data directory.

import json
import os
import uuid
import zipfile
from datetime import datetime
from pathlib import Path


class ProgressBuffer:
    """progress tracking and entities storage"""

    def __init__(self, books_dir: str = "books", data_dir: str = ".fwb_data"):
        """initialize directories"""
        self.books_dir = Path(books_dir)
        self.data_dir = Path(data_dir)

    def _get_book_data_dir(self, book_id: str) -> Path:
        """e.g. .fwb_data/10147/"""
        book_data_path = self.data_dir / str(book_id)
        book_data_path.mkdir(parents=True, exist_ok=True)
        return book_data_path

    def _get_source_zip_path(self, book_id: str) -> Path:
        """Get the file path for the book's source zip file."""
        return self.books_dir / f"book_{book_id}.zip"

    def get_source_chunk(self, book_id: str, chunk_id: int) -> str:
        """Retrieve a specific chapter from the book's zip file."""
        zip_path = self._get_source_zip_path(book_id)
        target_basename = f"{chunk_id}.txt"

        if not zip_path.is_file():
            return ""

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member_info in zf.infolist():
                    if (
                        not member_info.is_dir()
                        and os.path.basename(member_info.filename) == target_basename
                    ):
                        with zf.open(member_info.filename) as chapter_file:
                            return chapter_file.read().decode("utf-8", errors="ignore")
                return ""
        except (FileNotFoundError, zipfile.BadZipFile):
            return ""

    ## Save and retrieve reading progress for a book
    def save_progress(self, book_id: str, progress: int) -> None:
        """Save the reading progress for a book to 'progress.txt'."""
        book_data_dir = self._get_book_data_dir(book_id)
        progress_file = book_data_dir / "progress.txt"
        with open(progress_file, "w", encoding="utf-8") as f:
            f.write(str(progress))

    def get_progress(self, book_id: str) -> int:
        """Retrieve the reading progress from 'progress.txt'."""
        book_data_dir = self._get_book_data_dir(book_id)
        progress_file = book_data_dir / "progress.txt"
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return int(content) if content else 1
        except (FileNotFoundError, ValueError):
            return 1

    def reset_progress(self, book_id: str) -> None:
        """Reset the reading progress by deleting 'progress.txt'."""
        book_data_dir = self._get_book_data_dir(book_id)
        progress_file = book_data_dir / "progress.txt"
        try:
            os.remove(progress_file)
        except FileNotFoundError:
            pass

    ## Save and retrieve entities in the buffer for a book
    def save_entities_to_buffer(
        self, book_id: str, entities: str, starting_chunk_id: int, end_chunk_id: int
    ) -> None:
        """save entities as json"""
        book_data_dir = self._get_book_data_dir(book_id)
        entity_list = json.loads(entities) if isinstance(entities, str) else entities

        for entity in entity_list:
            entity_id = str(uuid.uuid4())
            doc = {
                "entity_id": entity_id,
                "entity": entity,
                "starting_chunk_id": starting_chunk_id,
                "end_chunk_id": end_chunk_id,
                "@timestamp": datetime.now().isoformat(),
            }
            # Save each entity document as its own JSON file
            entity_file_path = book_data_dir / f"{entity_id}.json"
            with open(entity_file_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2)

    def get_entities_from_buffer(self, book_id: str) -> list[dict]:
        """Retrieve all entities by reading all .json files from the book's data directory."""
        book_data_dir = self._get_book_data_dir(book_id)

        if not book_data_dir.exists():
            return []

        all_entities = []
        for file_path in book_data_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    all_entities.append(json.load(f))
            except (json.JSONDecodeError, IOError):
                print(f"Error reading {file_path}: skipping file.")
                # Ignore corrupted or unreadable files
                pass
        return all_entities

    def clear_buffer(self, book_id: str) -> None:
        """remove all json files"""
        book_data_dir = self._get_book_data_dir(book_id)
        if not book_data_dir.exists():
            return

        for file_path in book_data_dir.glob("*.json"):
            try:
                os.remove(file_path)
            except OSError:
                # Ignore errors if file is already gone
                pass

    def get_book_length(self, book_id: str) -> int:
        """get the number of chunks in total"""
        zip_path = self._get_source_zip_path(book_id)

        if not zip_path.is_file():
            return 0

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                count = 0
                for member_info in zf.infolist():
                    if not member_info.is_dir() and member_info.filename.endswith(
                        ".txt"
                    ):
                        basename = os.path.basename(member_info.filename)
                        filename_no_ext = os.path.splitext(basename)[0]
                        if filename_no_ext.isdigit():
                            count += 1
                return count
        except (FileNotFoundError, zipfile.BadZipFile):
            return 0
