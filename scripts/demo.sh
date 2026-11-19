#!/usr/bin/env bash
# Starts the Kaizen demo with one command, on macOS or Linux. Windows: scripts/demo.ps1.
#
#   bash scripts/demo.sh            check, install, build work/demo.db, start, open the browser
#   bash scripts/demo.sh --check    run the checks only and exit (exit code 1 if one failed)
#
# Options:
#   --fresh           delete work/demo.db and build it again (asks for a new password)
#   --local           use Ollama for suggestions even when ANTHROPIC_API_KEY is set
#   --llm-labels      label with the LLM instead of the TF-IDF baseline when the database is
#                     built (much slower; pair it with --fresh)
#   --api-port N      API port, default 8000 (the front end's /api proxy follows it)
#   --web-port N      front end port, default 5173
#   --no-browser      do not open the browser
#   --password-file F for automated testing only: read the demo password from the first
#                     line of F instead of asking. Keep F outside the repository.
#
# The password is asked once, when the database is built, and passed to the build script
# through KAIZEN_DEMO_PASSWORD for that one process. It is never printed or saved.
# Installs are skipped when backend/pyproject.toml and frontend/package-lock.json have not
# changed since the last one. Logs go to work/logs/. Ctrl+C stops the API and the front end.
set -euo pipefail

CHECK=0 FRESH=0 LOCAL=0 LLM_LABELS=0 NO_BROWSER=0
API_PORT=8000 WEB_PORT=5173 PASSWORD_FILE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --check) CHECK=1 ;;
        --fresh) FRESH=1 ;;
        --local) LOCAL=1 ;;
        --llm-labels) LLM_LABELS=1 ;;
        --no-browser) NO_BROWSER=1 ;;
        --api-port) API_PORT="${2:?--api-port needs a number}"; shift ;;
        --web-port) WEB_PORT="${2:?--web-port needs a number}"; shift ;;
        --password-file) PASSWORD_FILE="${2:?--password-file needs a path}"; shift ;;
        -h|--help) sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option $1, see: bash scripts/demo.sh --help" >&2; exit 2 ;;
    esac
    shift
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
WORK="$ROOT/work"
LOGS="$WORK/logs"
DB="$WORK/demo.db"
DB_BUILDING="$WORK/demo-building.db"
VENV="$BACKEND/.venv"
VENV_PYTHON="$VENV/bin/python"
VENV_STAMP="$VENV/kaizen-pyproject.sha256"
NODE_MODULES="$FRONTEND/node_modules"
NPM_STAMP="$NODE_MODULES/.kaizen-package-lock.sha256"
OLLAMA_MODEL="qwen2.5:7b"
FAILURES=0
CHILDREN=()

ok()   { printf '\033[32mok\033[0m    %s\n' "$1"; }
warn() { printf '\033[33mwarn\033[0m  %s\n' "$1"; }
step() { printf '..    %s\n' "$1"; }
info() { printf '      %s\n' "$1"; }
# Prints the problem and the fix. With --check it keeps going so every problem is listed.
fail() {
    printf '\033[31mFAIL\033[0m  %s\n' "$1"
    [[ -n "${2:-}" ]] && printf '      Fix: %s\n' "$2"
    FAILURES=$((FAILURES + 1))
    if [[ $CHECK -eq 0 ]]; then exit 1; fi
    return 0
}

case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) echo "On Windows use: powershell -ExecutionPolicy Bypass -File scripts\\demo.ps1" >&2; exit 2 ;;
esac

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
    else shasum -a 256 "$1" | cut -d' ' -f1; fi
}
stamp() { if [[ -f "$1" ]]; then tr -d '[:space:]' < "$1"; fi; }

stop_children() {
    local stopped=0 pid
    for pid in "${CHILDREN[@]+"${CHILDREN[@]}"}"; do
        if kill -0 "$pid" 2>/dev/null; then
            # Vite starts its own helper processes, so stop the children's children too.
            pkill -TERM -P "$pid" 2>/dev/null || true
            kill -TERM "$pid" 2>/dev/null || true
            stopped=1
        fi
    done
    for pid in "${CHILDREN[@]+"${CHILDREN[@]}"}"; do
        for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
        if kill -0 "$pid" 2>/dev/null; then pkill -KILL -P "$pid" 2>/dev/null || true; kill -KILL "$pid" 2>/dev/null || true; fi
    done
    if [[ ${#CHILDREN[@]} -gt 0 && $stopped -eq 1 ]]; then echo "Stopped the API and the front end."; fi
    CHILDREN=()
}
cleanup() { stop_children; rm -f "$DB_BUILDING"; }
trap cleanup EXIT
trap 'exit 130' INT TERM

version_ge() {  # version_ge 3.12.6 3.12
    [[ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" == "$2" ]]
}

log_tail() {
    if [[ -f "$1" ]]; then info "Last lines of ${1#"$ROOT"/}:"; tail -n 15 "$1" | sed 's/^/        /'; fi
}

url_ok() { curl -fsS -m 3 -o /dev/null "$1" 2>/dev/null; }

port_owner() {  # prints "name PID" or "unknown"; returns 1 if the port is free
    local line
    if command -v lsof >/dev/null 2>&1; then
        line="$(lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1" "$2}')"
        [[ -n "$line" ]] && { echo "$line"; return 0; }
    fi
    if command -v ss >/dev/null 2>&1; then
        line="$(ss -ltnpH "sport = :$1" 2>/dev/null | head -n1)"
        if [[ -n "$line" ]]; then
            echo "$line" | sed -n 's/.*users:(("\([^"]*\)",pid=\([0-9]*\).*/\1 \2/p' | grep . || echo "unknown"
            return 0
        fi
    fi
    if (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; then echo "unknown"; return 0; fi
    return 1
}

check_port() {
    local owner
    if owner="$(port_owner "$1")"; then
        if [[ "$owner" == "unknown" ]]; then
            fail "Port $1 ($2) is in use." "stop whatever is using it, or pick another port with --api-port / --web-port"
        else
            fail "Port $1 ($2) is in use by ${owner% *}, PID ${owner#* }." "stop it with: kill ${owner#* }   or pick another port with --api-port / --web-port"
        fi
    else
        ok "Port $1 is free ($2)"
    fi
}

# ---------------------------------------------------------------- checks

mkdir -p "$LOGS"

branch="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
if [[ -n "$branch" && "$branch" != "main" ]]; then
    warn "You are on branch $branch, not main. For the demo: git checkout main && git pull"
fi

PYTHON=""
for candidate in python3.12 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        v="$("$candidate" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || true)"
        if [[ -n "$v" ]] && version_ge "$v" 3.12; then PYTHON="$candidate"; PYTHON_VERSION="$v"; break; fi
    fi
done
if [[ -z "$PYTHON" ]]; then
    fail "Python 3.12 or newer was not found (tried python3.12, python3, python)." \
        "install Python 3.12 (macOS: brew install python@3.12; Ubuntu: sudo apt install python3.12 python3.12-venv)"
else
    ok "Python $PYTHON_VERSION ($PYTHON)"
fi
if [[ -x "$VENV_PYTHON" ]]; then
    v="$("$VENV_PYTHON" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || true)"
    if [[ -z "$v" ]] || ! version_ge "$v" 3.12; then
        fail "backend/.venv does not run Python 3.12 or newer." "delete backend/.venv and run this again"
    fi
fi

if ! command -v node >/dev/null 2>&1; then
    fail "Node was not found." "install Node 24 LTS from https://nodejs.org, then open a new terminal"
else
    v="$(node --version | sed 's/^v//')"
    major="${v%%.*}" rest="${v#*.}" minor="${rest%%.*}"
    if { [[ $major -eq 20 && $minor -ge 19 ]] || [[ $major -eq 22 && $minor -ge 12 ]] || [[ $major -gt 22 ]]; }; then
        ok "Node $v"
    else
        fail "Node $v is too old, Vite needs 20.19 or newer (22.12 or newer on the 22 line)." "install Node 24 LTS from https://nodejs.org"
    fi
fi
if ! command -v npm >/dev/null 2>&1; then
    fail "npm was not found." "it comes with Node: reinstall Node 24 LTS from https://nodejs.org"
else
    ok "npm $(npm --version)"
fi

# Which models the API (and an LLM-labelled build) will use.
if [[ -n "${ANTHROPIC_API_KEY:-}" && $LOCAL -eq 0 ]]; then
    ok "ANTHROPIC_API_KEY is set, so suggestions use the hosted models (add --local to use Ollama)"
else
    # Set even when Ollama is down, so starting Ollama later is enough, without a restart.
    export KAIZEN_SUGGEST_MODEL="ollama/$OLLAMA_MODEL"
    if [[ $LLM_LABELS -eq 1 ]]; then export KAIZEN_LABEL_MODEL="ollama/$OLLAMA_MODEL"; fi
    if ! tags="$(curl -fsS -m 3 http://localhost:11434/api/tags 2>/dev/null)"; then
        if [[ $LLM_LABELS -eq 1 && $FRESH -eq 1 ]]; then
            fail "Ollama is not running, and --llm-labels needs it to build the database." "start Ollama (ollama serve), then run this again"
        fi
        warn "Ollama is not running at http://localhost:11434. Suggestions will not work until you start it."
        info "Fix: start the Ollama app, or run: ollama serve. The rest of the demo works without it."
    elif ! grep -q "\"name\":\"$OLLAMA_MODEL\"" <<<"$tags"; then
        warn "Ollama is running but does not have $OLLAMA_MODEL. Suggestions will not work until it does."
        info "Fix: ollama pull $OLLAMA_MODEL   (about 4.7 GB)"
    else
        ok "Ollama is running with $OLLAMA_MODEL, suggestions use ollama/$OLLAMA_MODEL"
    fi
fi

check_port "$API_PORT" "API"
check_port "$WEB_PORT" "front end"

if [[ $CHECK -eq 1 ]]; then
    if [[ -x "$VENV_PYTHON" && "$(stamp "$VENV_STAMP")" == "$(sha256 "$BACKEND/pyproject.toml")" ]]; then ok "Back end installed and up to date"
    else info "Back end will be installed into backend/.venv on the next run (a few minutes)"; fi
    if [[ -d "$NODE_MODULES" && "$(stamp "$NPM_STAMP")" == "$(sha256 "$FRONTEND/package-lock.json")" ]]; then ok "Front end packages installed and up to date"
    else info "npm ci will run in frontend on the next run"; fi
    if [[ -f "$DB" && $FRESH -eq 0 ]]; then ok "Demo database work/demo.db exists"
    else info "work/demo.db will be built on the next run (about two minutes, asks for a password)"; fi
    echo
    if [[ $FAILURES -gt 0 ]]; then echo "$FAILURES check(s) failed. Fix them before the demo."; exit 1; fi
    echo "All checks passed."
    exit 0
fi

# ---------------------------------------------------------------- install

if [[ ! -x "$VENV_PYTHON" ]]; then
    if [[ -d "$VENV" ]]; then
        fail "backend/.venv exists but has no bin/python (it may come from Windows or a broken install)." "delete backend/.venv and run this again"
    fi
    step "Creating backend/.venv with Python $PYTHON_VERSION"
    "$PYTHON" -m venv "$VENV" || fail "Could not create backend/.venv." "run: $PYTHON -m venv backend/.venv   and read the error (Ubuntu needs python3.12-venv)"
fi
hash="$(sha256 "$BACKEND/pyproject.toml")"
if [[ "$(stamp "$VENV_STAMP")" == "$hash" ]]; then
    ok "Back end already installed and pyproject.toml unchanged"
else
    step "Installing the back end into backend/.venv (first time takes a few minutes, log in work/logs/pip-install.log)"
    if ! (cd "$BACKEND" && "$VENV_PYTHON" -m pip install --disable-pip-version-check -e ".[dev]") >"$LOGS/pip-install.log" 2>&1; then
        log_tail "$LOGS/pip-install.log"
        fail "pip install failed." "read work/logs/pip-install.log; a network problem usually fixes itself on a second run"
    fi
    echo "$hash" > "$VENV_STAMP"
    ok "Back end installed"
fi

hash="$(sha256 "$FRONTEND/package-lock.json")"
if [[ -d "$NODE_MODULES" && "$(stamp "$NPM_STAMP")" == "$hash" ]]; then
    ok "Front end packages already installed and package-lock.json unchanged"
else
    step "Running npm ci in frontend (log in work/logs/npm-ci.log)"
    if ! (cd "$FRONTEND" && npm ci --no-audit --no-fund) >"$LOGS/npm-ci.log" 2>&1; then
        log_tail "$LOGS/npm-ci.log"
        fail "npm ci failed." "read work/logs/npm-ci.log"
    fi
    echo "$hash" > "$NPM_STAMP"
    ok "Front end packages installed"
fi

# ---------------------------------------------------------------- database

if [[ $FRESH -eq 1 && -f "$DB" ]]; then rm -f "$DB"; ok "Deleted the old work/demo.db (--fresh)"; fi
if [[ -f "$DB" ]]; then
    ok "Demo database work/demo.db exists (use --fresh to rebuild it)"
else
    # Built under another name and renamed at the end, so a build that fails or is stopped
    # halfway never leaves a demo.db that looks finished.
    rm -f "$DB_BUILDING"
    step "Building the demo database work/demo.db"
    if [[ -n "$PASSWORD_FILE" ]]; then
        [[ -f "$PASSWORD_FILE" ]] || fail "Password file not found: $PASSWORD_FILE"
        IFS= read -r password < "$PASSWORD_FILE" || true
    else
        info "Choose one password for demo-qi, demo-manager and demo-admin (10 or more characters)."
        info "It is not shown, printed or saved. If you forget it, run again with --fresh."
        password=""
        for _ in 1 2 3; do
            IFS= read -rs -p "      Password: " password; echo
            [[ ${#password} -ge 10 ]] && break
            warn "That is too short, it needs 10 or more characters."
        done
    fi
    [[ ${#password} -ge 10 ]] || fail "No password of 10 or more characters was given." "run the script again"
    labeller=()
    if [[ $LLM_LABELS -eq 1 ]]; then labeller=(--labeller llm); fi
    info "Importing, de-identifying, labelling and grouping 2,300 synthetic comments, about two minutes."
    # The variable is set on this one command only, so no other process sees it.
    if ! (cd "$BACKEND" && KAIZEN_DEMO_PASSWORD="$password" "$VENV_PYTHON" scripts/demo_data.py "$DB_BUILDING" "${labeller[@]+"${labeller[@]}"}"); then
        unset password
        fail "Building the demo database failed." "read the error above, then run again"
    fi
    unset password
    mv "$DB_BUILDING" "$DB"
    ok "Demo database built"
fi

# ---------------------------------------------------------------- start

export KAIZEN_DATABASE_URL="sqlite:///$DB"
export KAIZEN_INDEX_PATH="$WORK/kaizen-passages.npz"
export KAIZEN_API_PORT="$API_PORT"

step "Starting the API on port $API_PORT and the front end on port $WEB_PORT (logs in work/logs)"
(cd "$BACKEND" && exec "$VENV_PYTHON" -m uvicorn kaizen.api.app:create_app --factory --host 127.0.0.1 --port "$API_PORT") \
    >"$LOGS/api.log" 2>"$LOGS/api.err.log" &
API_PID=$!
CHILDREN+=("$API_PID")
(cd "$FRONTEND" && exec node node_modules/vite/bin/vite.js --port "$WEB_PORT" --strictPort) \
    >"$LOGS/web.log" 2>"$LOGS/web.err.log" &
WEB_PID=$!
CHILDREN+=("$WEB_PID")

api_up=0 web_up=0 deadline=$((SECONDS + 60))
while [[ $api_up -eq 0 || $web_up -eq 0 ]]; do
    if ! kill -0 "$API_PID" 2>/dev/null; then
        log_tail "$LOGS/api.err.log"; fail "The API stopped while starting." "read work/logs/api.err.log"
    fi
    if ! kill -0 "$WEB_PID" 2>/dev/null; then
        log_tail "$LOGS/web.log"; log_tail "$LOGS/web.err.log"; fail "The front end stopped while starting." "read work/logs/web.log and web.err.log"
    fi
    if [[ $SECONDS -gt $deadline ]]; then
        if [[ $api_up -eq 0 ]]; then which="The API"; else which="The front end"; fi
        fail "$which did not answer within 60 seconds." "read the logs in work/logs, then run again"
    fi
    [[ $api_up -eq 1 ]] || { url_ok "http://127.0.0.1:$API_PORT/units" && api_up=1; } || true
    [[ $web_up -eq 1 ]] || { url_ok "http://localhost:$WEB_PORT/" && web_up=1; } || true
    [[ $api_up -eq 1 && $web_up -eq 1 ]] || sleep 0.5
done
url_ok "http://localhost:$WEB_PORT/api/units" || \
    fail "The front end is up but cannot reach the API through /api." "check that frontend/vite.config.ts reads KAIZEN_API_PORT, and read work/logs/web.log"
ok "API and front end are answering"

URL="http://localhost:$WEB_PORT"
cat <<EOF

Kaizen is running at $URL
API docs at http://localhost:$API_PORT/docs, logs in work/logs

Log in with the password chosen when work/demo.db was built:
  demo-qi        QI staff, all units. Upload a CSV, correct labels, rename and merge issues,
                 draft suggestions and accept, edit or reject them.
  demo-manager   Unit manager for 4B. Sees issues, comments and the comparison for 4B only,
                 and cannot change anything.
  demo-admin     Everything demo-qi can do, plus creating accounts (POST /users in the API docs).

Press Ctrl+C to stop both.
EOF
if [[ $NO_BROWSER -eq 0 ]]; then
    if command -v open >/dev/null 2>&1 && [[ "$(uname -s)" == "Darwin" ]]; then open "$URL"
    elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true; fi
fi

while true; do
    if ! kill -0 "$API_PID" 2>/dev/null; then log_tail "$LOGS/api.err.log"; fail "The API stopped." "read work/logs/api.err.log, then run again"; fi
    if ! kill -0 "$WEB_PID" 2>/dev/null; then log_tail "$LOGS/web.err.log"; fail "The front end stopped." "read work/logs/web.err.log, then run again"; fi
    sleep 1
done
