#!/usr/bin/env bash
# Gordon — presenter's demo script. Six beats, ENTER-paced (or --auto).
#
#   ./scripts/demo.sh          press ENTER to advance between beats
#   ./scripts/demo.sh --auto   self-running, ~15s per beat
#
# Prereq: ./start.sh already ran (engine :8001, backend :8765, overlay window).
# Each beat POSTs a capture event; the overlay pops the roast card and speaks.
set -euo pipefail

BACKEND="${BACKEND:-http://127.0.0.1:8765}"
AUTO=false; [ "${1:-}" = "--auto" ] && AUTO=true

bold()  { printf '\033[1m%s\033[0m\n' "$1"; }
pause() {
  if $AUTO; then sleep 15; else read -r -p $'\n\033[2m[ENTER for next beat]\033[0m '; fi
}

curl -sf -m 2 "$BACKEND/health" >/dev/null || { echo "backend not up — run ./start.sh first"; exit 1; }

fire() { # personality, prompt
  python3 - "$BACKEND" "$1" "$2" <<'PY'
import json, sys, urllib.request, uuid, datetime
backend, personality, prompt = sys.argv[1], sys.argv[2], sys.argv[3]
event = {
    "event_id": str(uuid.uuid4()),
    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "source": "chat_application", "application": "cursor",
    "prompt_text": prompt, "selected_model": "unknown",
    "screenshot_path": None, "session_id": "demo-day",
    "personality_id": personality,
}
req = urllib.request.Request(backend + "/api/events", data=json.dumps(event).encode(),
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=45) as r:
    e = json.load(r)["evaluation"]
print(f'  score {e["overall_score"]:>3}  |  {e["primary_category"]}  |  action: {e["action"]}')
print(f'  ROAST    {e["roast"]}')
print(f'  LESSON   {e["lesson"]}')
better = e["improved_prompt"].replace("\n", "\n           ")
print(f'  SUGGESTS {better[:300]}')
src = e.get("source")
if src:
    print(f'  SOURCE   {src["date"]} — {src["url"]}')
PY
}

bold "GORDON DEMO — 'a day of vibecoding'"
echo "Overlay window should be visible. Each beat = one captured prompt."

bold $'\n[1/6] The classic. Someone actually typed this.'
echo '  > "Make this work"'
fire angry_chef "Make this work"
pause

bold $'\n[2/6] The model was not in that meeting.'
echo '  > "Use the same approach as the other file"'
fire angry_chef "Use the same approach as the other file"
pause

bold $'\n[3/6] Frontier check — 2018 called, cited with receipts.'
echo '  > React class component with componentWillMount...'
fire angry_chef "Write me a React class component using componentWillMount to fetch data from my API"
pause

bold $'\n[4/6] The 3000-line paste to ask about one line.'
fire angry_chef "Here is my whole main.py, all 3000 lines: [pasted]. Anyway can you check line 12 for me"
pause

bold $'\n[5/6] Personality switch: the Disappointed Professor takes this one.'
echo '  > payment code straight to prod, no tests'
fire disappointed_professor "Write a payment processing module, I'll push it straight to prod, no tests needed"
pause

bold $'\n[6/6] And when you prompt WELL — Gordon admits it. No buzzer.'
fire angry_chef "In src/api/users.py the get_user endpoint returns 500 when user_id is a UUID string instead of the expected 404. Stack trace: ValueError at line 42 (int coercion). Fix the coercion at line 42 to return 404 for non-integer IDs, and add a pytest regression test for the UUID case."

bold $'\nFinale: open the dashboard — kitchen rating, category averages, history.'
echo "  $BACKEND/site/design_handoff_gordon_overlay/Gordon.dc.html"
