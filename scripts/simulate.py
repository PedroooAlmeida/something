"""Headless demo: drives the state machine + triggers with a scripted session.

No screen capture, no OCR, no macOS deps — proves the semantic layer end-to-end
and writes real JSON events into roast_events/. Run: python scripts/simulate.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capture.config import Config
from capture.emitter import Emitter
from capture.machine import Machine
from capture.triggers import TriggerEngine

# Fake conversation the "assistant" writes into; the machine measures its growth.
conversation = [""]


def read_conversation():
    return conversation[0]


def run():
    cfg = Config()
    cfg.cooldown_s = 0          # show every trigger in the demo
    cfg.kind_cooldown_s = 0
    cfg.model_enabled = False   # semantic layer only — no API calls from the demo
    emitter = Emitter(cfg.events_dir)
    machine = Machine(cfg, read_conversation=read_conversation)
    engine = TriggerEngine(cfg, emitter, debug=True)

    t = [1000.0]

    def tick(dt, composer=None, conv=False, scrolled=False):
        t[0] += dt
        for sem in machine.feed(t[0], composer_text=composer,
                                conv_changed=conv, scrolled=scrolled):
            print(f"  sem: {sem.kind} {sem.data}")
            engine.process(sem, app="SimulatedApp", window_title="demo session")

    def submit_shown(text):
        """User's message appears in the conversation region."""
        conversation[0] += "\nUser: " + text

    def stream(chars, seconds=3.0, steps=6):
        """Assistant streams a response of `chars` chars."""
        chunk = "x" * (chars // steps)
        for _ in range(steps):
            conversation[0] += chunk
            tick(seconds / steps, conv=True)

    def settle():
        tick(1.6)   # stream settles -> RESPONSE_DONE

    print("\n--- scene 1: lazy + vague prompt, typed in under 2s ---")
    tick(0.3, composer="make this")
    tick(0.4, composer="make this work")
    tick(0.3, composer="")                      # composer empties
    submit_shown("make this work"); tick(0.2, conv=True)   # corroboration

    print("\n--- scene 2: assistant answers, user replies in 3s, no scroll ---")
    stream(1800); settle()
    tick(3.0, composer="ok but why")            # reading_ended -> no_read

    print("\n--- scene 3: 5000-char paste ---")
    tick(0.5, composer="ok but why" + "y" * 5000)   # token_dump
    tick(0.3, composer="")
    submit_shown("big paste"); tick(0.2, conv=True)
    stream(400); settle()

    print("\n--- scene 4: same question three times ---")
    for i, txt in enumerate(["fix the login bug",
                             "fix the login bug please",
                             "please fix the login bug now"]):
        tick(4.0, composer=txt[:6])
        tick(2.5, composer=txt)
        tick(0.3, composer="")
        submit_shown(txt); tick(0.2, conv=True)
        stream(300); settle()

    print("\n--- scene 5: API key in the prompt ---")
    tick(4.0, composer="use this key sk-ant-abc123def456ghi789jkl012 to call the api")
    tick(0.3, composer="")
    submit_shown("use this key"); tick(0.2, conv=True)

    print(f"\nevents written to {cfg.events_dir}/:")
    for f in sorted(os.listdir(cfg.events_dir)):
        print(f"  {f}")


if __name__ == "__main__":
    run()
