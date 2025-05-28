import os
import re
import argparse


def rename_chapter_files(directory_path):
    """
    Renames chapter files in the given directory.
    Pattern: 0585_1第五百八十八章_古神棺椁.txt -> 585.txt
    """
    if not os.path.isdir(directory_path):
        print(f"Error: Directory not found: {directory_path}")
        return

    renamed_count = 0
    skipped_count = 0
    error_count = 0

    print(f"\nProcessing directory: {directory_path}")

    for filename in os.listdir(directory_path):
        # Regex to capture the initial number sequence before the first underscore
        # It expects one or more digits at the beginning, followed by an underscore.
        # Example: "0585_1..." -> captures "0585"
        # Example: "1192_1..." -> captures "1192"
        match = re.match(r"(\d+)_.*\.txt$", filename)

        if match:
            original_number_str = match.group(1)  # This is the "0585", "1192", etc.

            # Convert to integer to remove leading zeros, then back to string
            try:
                new_base_name_int = int(original_number_str)
                new_base_name_str = str(new_base_name_int)
            except ValueError:
                print(f"  Skipping (bad number format): {filename}")
                skipped_count += 1
                continue

            new_filename = f"{new_base_name_str}.txt"
            old_filepath = os.path.join(directory_path, filename)
            new_filepath = os.path.join(directory_path, new_filename)

            if old_filepath == new_filepath:
                # print(f"  Skipping (already named correctly): {filename}")
                skipped_count += 1
                continue

            if os.path.exists(new_filepath):
                print(
                    f"  Error: Target file '{new_filename}' already exists. Skipping rename for '{filename}'."
                )
                error_count += 1
                continue

            try:
                os.rename(old_filepath, new_filepath)
                print(f"  Renamed: '{filename}' -> '{new_filename}'")
                renamed_count += 1
            except OSError as e:
                print(f"  Error renaming '{filename}' to '{new_filename}': {e}")
                error_count += 1
        else:
            # print(f"  Skipping (no match): {filename}") # Optional: print files that don't match
            pass  # Do nothing for files that don't match the pattern

    print(f"Finished processing {directory_path}:")
    print(
        f"  Renamed: {renamed_count}, Skipped: {skipped_count}, Errors: {error_count}"
    )
    return renamed_count, skipped_count, error_count


def main():
    parser = argparse.ArgumentParser(
        description="Batch rename chapter files in subdirectories."
    )
    parser.add_argument(
        "base_directory",
        help="The base directory containing book subdirectories (e.g., 'books' which contains 'book_41814', 'book_45862', etc.).",
    )

    args = parser.parse_args()

    if not os.path.isdir(args.base_directory):
        print(f"Error: Base directory '{args.base_directory}' not found.")
        return

    total_renamed = 0
    total_skipped = 0
    total_errors = 0

    print(f"Starting batch rename process in base directory: {args.base_directory}")

    for item in os.listdir(args.base_directory):
        item_path = os.path.join(args.base_directory, item)
        # Process only if it's a directory and starts with "book_"
        if os.path.isdir(item_path) and item.startswith("book_"):
            renamed, skipped, errors = rename_chapter_files(item_path)
            total_renamed += renamed
            total_skipped += skipped
            total_errors += errors
        else:
            print(f"Skipping non-book directory or file: {item_path}")

    print("\n--- Batch Rename Summary ---")
    print(f"Total files renamed: {total_renamed}")
    print(f"Total files skipped: {total_skipped}")
    print(f"Total errors during rename: {total_errors}")
    print("Batch renaming complete.")


if __name__ == "__main__":
    main()
