""" Resource to print error in presntable format"""

import textwrap

def pretty_print_error(error_message):
    """
    Formats and wraps an error message for readability.
    
    Args:
        error_message (str): The error message to be formatted.
    
    Returns:
        str: The formatted error message with wrapped lines.
    """
    try:
        # Convert escape sequences (like \n and \t) to their actual characters.
        unescaped_message = error_message.encode('utf-8').decode('unicode_escape')
    except UnicodeDecodeError:
        # If decoding fails, just use the raw error message.
        unescaped_message = error_message

    # Use textwrap to wrap the entire message to 100 characters for readability.
    wrapped_message = textwrap.fill(unescaped_message, width=100)

    return wrapped_message
