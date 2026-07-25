#!/usr/bin/env bash
# Gordon demo driver — fires four prompt scenarios through the LIVE backend so the
# overlay pops on cue while you record. Run it once the app is open.
#   ./demo.sh
set -e
B=https://gordon-platform.fly.dev
fire() {  # fire <id> <prompt>
  curl -s -X POST $B/api/events -H "Content-Type: application/json" \
    -d "{\"event_id\":\"demo-$1-$(od -An -N2 -tu2 < /dev/urandom | tr -d ' ')\",\"timestamp\":\"2026-07-25T12:00:00Z\",\"source\":\"chat_application\",\"application\":\"supported_ai_tool\",\"prompt_text\":$2,\"selected_model\":\"unknown\",\"personality_id\":\"angry_chef\"}" \
    -o /dev/null -w "  fired: %{http_code}\n"
}

echo "① vague prompt — expect BURNT, high severity, buzzer"
fire vague '"just make it work"'
sleep 9

echo "② token dump — expect roast on token conservation"
fire tokens '"Hey so quick background, we are a Series A company building restaurant tooling, founded 2021 by three ex-hospitality people, our mission is to make back-of-house software invisible, Q3 roadmap is loyalty gift cards a new onboarding flow and the checkout rewrite, here is our standup from Tuesday and our entire design doc plus utils.ts logger.ts theme.ts and the seed script because I want you to have full context. Also Priya ordered katsu curry again. Anyway. Checkout sometimes fails. Make it not do that."'
sleep 9

echo "③ outdated model — expect frontier-awareness roast"
fire outdated '"convert this component to jQuery and make sure it works on Python 2"'
sleep 9

echo "④ a genuinely good prompt — expect SERVICEABLE, no yelling"
fire good '"In auth.ts, login() throws JWT expired for tokens that are still valid, only after ~1h. Here is the handler [paste]. Find the root cause, fix the null case, and explain why it only triggers after an hour without changing the public API."'
echo "done."
