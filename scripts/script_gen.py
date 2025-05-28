import argparse
import os

# --- Configuration ---
# Define constants for the default values
DEFAULT_PYTHON_EXECUTABLE = "python"
DEFAULT_SCRIPT_TO_RUN = "scripts/crawl_fiction.py"
DEFAULT_THREADS = 20
DEFAULT_OUTPUT_DIR_ARG = "books"
DEFAULT_END_CHAPTER_VAL = 4000  # Renamed to avoid conflict
DEFAULT_SAMPLE_CHAPTER_URL_TEMPLATE = (
    "https://8520b295ef767.fk6k.cc/index/{book_id}/1.html"
)

# These will be updated in main() if CLI args are provided
PYTHON_EXECUTABLE = DEFAULT_PYTHON_EXECUTABLE
SCRIPT_TO_RUN = DEFAULT_SCRIPT_TO_RUN
THREADS_COUNT = DEFAULT_THREADS  # Renamed to avoid conflict with argparse 'threads'
OUTPUT_DIR_ARG_VAL = DEFAULT_OUTPUT_DIR_ARG  # Renamed
END_CHAPTER_VAL = DEFAULT_END_CHAPTER_VAL  # Renamed
SAMPLE_CHAPTER_URL_TEMPLATE = DEFAULT_SAMPLE_CHAPTER_URL_TEMPLATE


def generate_commands(id_filepath, current_end_chapter):  # Pass end_chapter explicitly
    """
    Reads book IDs from a file and generates crawler commands.
    Returns a list of command strings.
    """
    if not os.path.isfile(id_filepath):
        print(f"Error: ID file not found: {id_filepath}")
        return []

    commands = []
    try:
        with open(id_filepath, "r", encoding="utf-8") as f:
            for line in f:
                book_id = line.strip()
                if book_id.isdigit():
                    sample_url = SAMPLE_CHAPTER_URL_TEMPLATE.format(book_id=book_id)

                    command = (
                        f"{PYTHON_EXECUTABLE} {SCRIPT_TO_RUN} "
                        f"--threads {THREADS_COUNT} "  # Use the correctly scoped variable
                        f"--output {OUTPUT_DIR_ARG_VAL} "  # Use the correctly scoped variable
                        f"--start_chapter 1 "
                        f"--end_chapter {current_end_chapter} "  # Use the passed end_chapter
                        f'"{sample_url}"'
                    )
                    commands.append(command)
                elif book_id:
                    print(
                        f"Warning: Skipping invalid ID line: '{book_id}' in {id_filepath}"
                    )
    except IOError as e:
        print(f"Error reading ID file {id_filepath}: {e}")
        return []

    return commands


def main():
    parser = argparse.ArgumentParser(
        description="Generate crawler commands from a list of book IDs."
    )
    parser.add_argument(
        "id_file", help="Path to the text file containing book IDs, one ID per line."
    )
    parser.add_argument(
        "--output_script",
        help="Optional: Path to a shell script file where commands will be written (e.g., run_all.sh). If not provided, commands are printed to console.",
    )

    # Use the DEFAULT constants for argparse defaults
    parser.add_argument(
        "--end_chapter",
        type=int,
        default=DEFAULT_END_CHAPTER_VAL,
        help=f"Optional: Override the default end_chapter value for all generated commands. Default is {DEFAULT_END_CHAPTER_VAL}.",
    )
    parser.add_argument(
        "--python_exe",
        default=DEFAULT_PYTHON_EXECUTABLE,
        help=f"Python executable to use (default: {DEFAULT_PYTHON_EXECUTABLE}).",
    )
    parser.add_argument(
        "--crawler_script",
        default=DEFAULT_SCRIPT_TO_RUN,
        help=f"Path to the crawler script (default: {DEFAULT_SCRIPT_TO_RUN}).",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=DEFAULT_THREADS,
        help=f"Number of threads for the crawler (default: {DEFAULT_THREADS}).",
    )
    parser.add_argument(
        "--output_books_dir",
        default=DEFAULT_OUTPUT_DIR_ARG,
        help=f"Output directory for the crawler's '--output' argument (default: {DEFAULT_OUTPUT_DIR_ARG}).",
    )
    parser.add_argument(
        "--url_template",
        default=DEFAULT_SAMPLE_CHAPTER_URL_TEMPLATE,
        help=f"URL template for generating sample chapter URLs (default: '{DEFAULT_SAMPLE_CHAPTER_URL_TEMPLATE}').",
    )

    args = parser.parse_args()

    # Declare global and then assign from args
    global PYTHON_EXECUTABLE, SCRIPT_TO_RUN, THREADS_COUNT, OUTPUT_DIR_ARG_VAL, END_CHAPTER_VAL, SAMPLE_CHAPTER_URL_TEMPLATE
    PYTHON_EXECUTABLE = args.python_exe
    SCRIPT_TO_RUN = args.crawler_script
    THREADS_COUNT = args.threads  # Assign to the renamed global
    OUTPUT_DIR_ARG_VAL = args.output_books_dir  # Assign to the renamed global
    END_CHAPTER_VAL = (
        args.end_chapter
    )  # Use the value from args (which includes its own default)
    SAMPLE_CHAPTER_URL_TEMPLATE = args.url_template

    # Pass the effectively chosen end_chapter to generate_commands
    generated_commands = generate_commands(args.id_file, END_CHAPTER_VAL)

    if not generated_commands:
        print("No commands were generated.")
        return

    if args.output_script:
        try:
            with open(args.output_script, "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\n")
                f.write("# Generated crawler commands\n\n")
                for cmd in generated_commands:
                    f.write(cmd + "\n")
            os.chmod(args.output_script, 0o755)
            print(
                f"Successfully wrote {len(generated_commands)} commands to {args.output_script}"
            )
            print(f"You can now run: ./{args.output_script}")
        except IOError as e:
            print(f"Error writing commands to script file {args.output_script}: {e}")
    else:
        print("\nGenerated commands (print to console):\n" + "=" * 40)
        for cmd in generated_commands:
            print(cmd)
        print("=" * 40)


if __name__ == "__main__":
    main()
