"""Action router (PRD section 14).

Every adapter exposes trigger(category, severity, message). On a prompt violation
the router fans the event out to all enabled adapters. Registered webhooks receive:

    {
      "event": "prompt_violation",
      "category": "token_conservation",
      "severity": 2,
      "message": "Repeated 4,000 tokens of context"
    }
"""
import json
import threading
import urllib.request

from . import db

WEBHOOK_TIMEOUT = 4


class ConsoleAdapter:
    """Always-on adapter so the demo has visible output even with zero hardware."""
    name = "console"

    def trigger(self, category: str, severity: int, message: str):
        print(f"[action:{self.name}] severity={severity} category={category} :: {message}")


class WebhookAdapter:
    """POSTs the violation event to every registered webhook that matches
    the category filter and severity threshold. This is how the buzzer, smart
    light, servo, or Slack bridge subscribes — they're all just webhook receivers."""
    name = "webhook"

    def trigger(self, category: str, severity: int, message: str):
        payload = json.dumps({
            "event": "prompt_violation",
            "category": category,
            "severity": severity,
            "message": message,
        }).encode()
        hooks = db.rows("SELECT * FROM webhooks WHERE enabled=1 AND min_severity<=?", (severity,))
        for hook in hooks:
            cats = json.loads(hook.get("categories") or "[]")
            if cats and category not in cats:
                continue
            threading.Thread(target=self._post, args=(hook["url"], payload), daemon=True).start()

    @staticmethod
    def _post(url: str, payload: bytes):
        try:
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"},
                                         method="POST")
            urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT)
            print(f"[action:webhook] delivered to {url}")
        except Exception as exc:
            print(f"[action:webhook] delivery to {url} failed: {exc}")


ADAPTERS = [ConsoleAdapter(), WebhookAdapter()]


def dispatch(category: str, severity: int, message: str):
    """Fan a violation out to every adapter. severity 0 = no violation, no action."""
    if severity < 1:
        return
    for adapter in ADAPTERS:
        try:
            adapter.trigger(category, severity, message)
        except Exception as exc:
            print(f"[action:{adapter.name}] adapter error: {exc}")
