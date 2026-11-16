#!/usr/bin/env bash
# Run from any directory after installing backend[dev] in .venv.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONHASHSEED=4310
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=1
export NUMBA_NUM_THREADS=1
export KAIZEN_EMBED_CACHE="${KAIZEN_EMBED_CACHE:-$PWD/work/model-cache}"
export HF_HOME="$PWD/work/huggingface"
export XDG_CACHE_HOME="$PWD/work/cache"
export HF_HUB_DISABLE_TELEMETRY=1
export TLDEXTRACT_CACHE="$PWD/work/tld-cache"
mkdir -p work
PYTHON="${KAIZEN_PYTHON:-$PWD/.venv/bin/python}"
"$PYTHON" -m kaizen.evaluation.generate > work/generation-audit.json
if [[ "${1:-}" == "--with-public" ]]; then
    shift
    "$PYTHON" backend/scripts/fetch_fft_comments.py
    set -- --public-csv data/raw/fft-see-and-convey.csv "$@"
fi
"$PYTHON" -m kaizen.evaluation.run "$@"
"$PYTHON" -m pytest backend/tests -q
"$PYTHON" scripts/check_repo.py
