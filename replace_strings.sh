#!/bin/env bash
#
# MIT License
#
# (C) Copyright 2025 Hewlett Packard Enterprise Development LP
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
set -e

function err_exit {
    echo "ERROR: $*" 1>&2
    exit 1
}

# Usage: replace_strings.sh <old string> <new string> <target file>

[[ $# -eq 3 ]] || err_exit "$0 requires exactly 3 arguments but received $#. Invalid arguments: $*"
[[ -n $1 ]] || err_exit "First argument may not be blank. Invalid argument: $1"
[[ -n $2 ]] || err_exit "Second argument may not be blank. Invalid argument: $2"
[[ -n $3 ]] || err_exit "Third argument may not be blank. Invalid argument: $3"
[[ -e $3 ]] || err_exit "Third argument must be a file but $3 does not exist."
[[ -f $3 ]] || err_exit "Third argument must be a file but $3 is not a regular file."

# Create temporary file
tmpfile=$(mktemp)

# Do replacement
sed "s/$1/$2/g" "$3" > "$tmpfile"

# Show diff
if ! diff "$3" "$tmpfile" ; then
    # diff returned non-0, which means there was a difference.
    # This is what we want -- it means the replacement was done.

    # Copy the tempfile over the original
    cp "$tmpfile" "$3"

    # Remove the tempfile
    rm "$tmpfile"
    
    # Exit successfully
    exit 0
fi

# Remove the tempfile
rm "$tmpfile"

err_exit "The specified arguments ($*) resulted in no replacement being performed"
