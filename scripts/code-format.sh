#!/bin/bash

poetry run black -t py310 -l 88 hg_mcp tests

# Remove trailing whitespace in project .py files
find hg_mcp tests -name "*.py" -exec sed -i 's/[[:space:]]*$//' {} \;

