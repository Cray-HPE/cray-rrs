#
# MIT License
#
#  (C) Copyright 2025 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
"""Resource to print error in presntable format"""

import textwrap


def pretty_print_error(error_message: str) -> str:
    """
    Formats and wraps an error message for readability.

    Args:
        error_message (str): The error message to be formatted.

    Returns:
        str: The formatted error message with wrapped lines.
    """
    try:
        # Convert escape sequences (like \n and \t) to their actual characters.
        unescaped_message = error_message.encode("utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        # If decoding fails, just use the raw error message.
        unescaped_message = error_message

    # Use textwrap to wrap the entire message to 100 characters for readability.
    wrapped_message = textwrap.fill(unescaped_message, width=100)

    return wrapped_message
