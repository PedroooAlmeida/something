#!/usr/bin/env python3
"""
Gordon — terminal demo. Type a prompt, he scores it through the live backend,
prints the roast, and SAYS IT OUT LOUD (macOS `say`, full volume).

  python3 gordon.py

Also pops the overlay if the desktop app or browser overlay is open (same
backend WebSocket). Ctrl-C to quit.
"""
import json, subprocess, time, urllib.request

BACKEND = "https://gordon-platform.fly.dev"

# crank system volume + pick a voice with some menace
subprocess.run(["osascript", "-e", "set volume output volume 100"], capture_output=True)
VOICE = "Daniel"  # British; good angry-chef energy
if subprocess.run(["say", "-v", VOICE, ""], capture_output=True).returncode != 0:
    VOICE = None  # fall back to the default system voice

def say(text):
    cmd = ["say"] + (["-v", VOICE] if VOICE else []) + ["-r", "190", text]
    subprocess.run(cmd)

ORANGE, RED, DIM, RESET = "\033[38;5;208m", "\033[1;31m", "\033[2m", "\033[0m"
print(f"{ORANGE}🔥 Gordon is watching. Send a prompt — he'll tell you what's wrong with it. Loudly.{RESET}")
print(f"{DIM}   (Ctrl-C to quit){RESET}")

while True:
    try:
        prompt = input(f"\n{ORANGE}You ›{RESET} ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nGordon: Finally. Some peace.")
        break
    if not prompt:
        continue

    body = json.dumps({
        "event_id": f"term-{int(time.time() * 1000)}",
        "timestamp": "2026-07-25T12:00:00Z",
        "source": "chat_application",
        "application": "supported_ai_tool",
        "prompt_text": prompt,
        "selected_model": "unknown",
        "personality_id": "angry_chef",
    }).encode()

    req = urllib.request.Request(BACKEND + "/api/events", data=body,
                                headers={"Content-Type": "application/json"})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=25))
    except Exception as e:
        print(f"{RED}backend unreachable:{RESET} {e}")
        continue

    ev = data.get("evaluation", {})
    roast = ev.get("roast", "")
    score = ev.get("overall_score", "?")
    sev = ev.get("severity", 0)
    fix = ev.get("improved_prompt", "")

    print(f"\n{RED}GORDON [{score}/100 · severity {sev}]{RESET}")
    print(f"  {roast}")
    if fix:
        print(f"{DIM}  try instead: {fix}{RESET}")
    say(roast)
