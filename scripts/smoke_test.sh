#!/usr/bin/env bash
# Clean-clone smoke test: clone the repo, start it with Docker, upload a sample PDF, ask one
# question and check the answer carries a valid source.
#
# Needs ANTHROPIC_API_KEY (in the environment, or in env/.env of this repo), Docker, curl and
# python3. Port 8080 must be free, so stop any other running copy of the app first.
set -euo pipefail

BASE=http://localhost:8080
TIMEOUT_S=900  # the first build downloads the models
QUESTION="How many days is the notice period?"
SAMPLE_TEXT="The notice period is thirty days."

repo=$(git rev-parse --show-toplevel)
key=${ANTHROPIC_API_KEY:-}
if [ -z "$key" ] && [ -f "$repo/env/.env" ]; then
  key=$(sed -n 's/^ANTHROPIC_API_KEY=//p' "$repo/env/.env")
fi
[ -n "$key" ] || { echo "FAIL: ANTHROPIC_API_KEY is not set"; exit 1; }
if curl -s -o /dev/null "$BASE"; then
  echo "FAIL: something already answers on $BASE. Stop it first (docker compose down)."
  exit 1
fi

work=$(mktemp -d)
cleanup() {
  (cd "$work/clone" 2>/dev/null && docker compose down -v >/dev/null 2>&1) || true
  rm -rf "$work"
}
trap cleanup EXIT

echo "1/5 Cloning $repo"
git clone -q "$repo" "$work/clone"
cd "$work/clone"
echo "ANTHROPIC_API_KEY=$key" > env/.env

echo "2/5 docker compose up --build (the first build takes a while)"
docker compose up --build -d >/dev/null

wait_for() {  # wait_for <description> <command...>
  local what=$1; shift
  local waited=0
  until "$@" >/dev/null 2>&1; do
    sleep 5; waited=$((waited + 5))
    [ $waited -lt $TIMEOUT_S ] || { echo "FAIL: timed out waiting for $what"; docker compose logs --tail 40 api; exit 1; }
  done
}

healthy() { curl -sf "$BASE/api/health" | python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin)["healthy"] else 1)'; }
echo "3/5 Waiting for /api/health"
wait_for "a healthy api" healthy

echo "4/5 Uploading a sample PDF"
docker compose exec -T api python -c "
import sys, pymupdf
doc = pymupdf.open()
page = doc.new_page()
page.insert_text((72, 72), '1 Termination', fontsize=24)
page.insert_text((72, 120), '$SAMPLE_TEXT', fontsize=11)
sys.stdout.buffer.write(doc.tobytes())
" > "$work/sample.pdf"
curl -sf -F "files=@$work/sample.pdf;filename=sample.pdf" "$BASE/api/documents" >/dev/null

doc_status() { curl -sf "$BASE/api/documents" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["status"])'; }
ready() { [ "$(doc_status)" = ready ]; }
wait_for "the document to be ready" ready

echo "5/5 Asking: $QUESTION"
curl -sf -X POST "$BASE/api/chat" -H 'Content-Type: application/json' \
  -d "{\"question\": \"$QUESTION\", \"history\": []}" > "$work/answer.json"

python3 - "$work/answer.json" <<'PY'
import json, re, sys

reply = json.load(open(sys.argv[1]))
print("Answer:", reply["answer"])
cited = re.findall(r"\[(c\d+(?:, c\d+)*)\]", reply["answer"])
ids = [i for group in cited for i in group.split(", ")]
if not ids or any(i not in reply["sources"] for i in ids):
    sys.exit("FAIL: the answer has no valid source tag")
source = reply["sources"][ids[0]]
if source["filename"] != "sample.pdf":
    sys.exit(f"FAIL: unexpected source {source}")
if "thirty" not in reply["answer"].lower() and "30" not in reply["answer"]:
    sys.exit("FAIL: the answer does not mention thirty days")
print("Source:", source["filename"], "p.", source["page_start"], source["heading_path"])
print("PASS")
PY
