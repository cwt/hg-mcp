#!/bin/bash

CPU_CORES=$(lscpu | awk '/^Core\(s\) per socket:/ {c=$4} /^Socket\(s\):/ {s=$2} END {print c * s}')

# cleanup
rm -rf */__pycache__ .pytest_cache .coverage

# update existing packages as defined on pyproject.toml
poetry update

# install current project as editable
pip install -q -e .[speed]

# regenerate poetry.lock based on installed/updated packages
rm -f poetry.lock && poetry lock --no-cache

# run unit tests
# Coverage threshold set to 50% (v0.8.1):
# - Error handling paths not fully exercised
# - helpers.py (37%) contains utilities hard to test without extensive mocking
# - hggit.py (33%) requires Git-backed repos for full testing
# - Many tools are thin wrappers over run_hg_command()
# All 44 functional tests pass - coverage is aspirational target for future
PYTHONPATH=. poetry run pytest tests/ -n $CPU_CORES --cov=hg_mcp --cov-report=term-missing --cov-fail-under=50

