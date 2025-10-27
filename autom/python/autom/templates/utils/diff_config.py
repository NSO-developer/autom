import difflib
import os
from robot.api.deco import keyword

@keyword('Assert No Diff')
def assert_no_diff(file1, file2):
    """
    Compares two strings or file contents and asserts that there are no differences.
    If differences are found, it fails the test and logs the diff.

    Args:
        text1_source (str): The first string or path to the first file.
        text2_source (str): The second string or path to the second file.
        fromfile (str): Label for the first file in the diff output.
        tofile (str): Label for the second file in the diff output.
    """
    diff_output = get_unified_diff(file1, file2, 'Expected', 'Actual')
    if diff_output:
        raise AssertionError(f"Files or strings differ:\n{diff_output}")
    else:
        print("No differences found.")

def _read_file_content(self, file_path):
    """Helper to read file content, returning a list of lines."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.readlines()

def get_unified_diff(text1_source, text2_source, fromfile='file1', tofile='file2'):
    """
    Compares two strings or file contents and returns a unified diff.

    Args:
        text1_source (str): The first string or path to the first file.
        text2_source (str): The second string or path to the second file.
        fromfile (str): Label for the first file in the diff output.
        tofile (str): Label for the second file in the diff output.

    Returns:
        str: A string containing the unified diff output.
    """
    try:
        # Check if sources are file paths or direct strings
        if os.path.exists(text1_source) and os.path.isfile(text1_source):
            text1_lines = _read_file_content(text1_source)
        else:
            text1_lines = [line + '\n' for line in text1_source.splitlines()]

        if os.path.exists(text2_source) and os.path.isfile(text2_source):
            text2_lines = _read_file_content(text2_source)
        else:
            text2_lines = [line + '\n' for line in text2_source.splitlines()]

    except FileNotFoundError as e:
        return f"Error: {e}"

    diff_generator = difflib.unified_diff(
        text1_lines, text2_lines,
        fromfile=fromfile, tofile=tofile,
        lineterm='' # Prevent adding extra newlines if lines already have them
    )
    return ''.join(list(diff_generator))
