"""Dashboard / progress calculations (PRD section 13)."""
import json

from . import db

CATEGORIES = [
    "prompt_specificity", "token_conservation", "frontier_awareness",
    "tool_selection", "context_management", "verification",
]

CATEGORY_LABELS = {
    "prompt_specificity": "Prompt Specificity",
    "token_conservation": "Token Conservation",
    "frontier_awareness": "Frontier Awareness",
    "tool_selection": "Tool Selection",
    "context_management": "Context Management",
    "verification": "Verification",
}


def _kitchen_rating(avg_score: float) -> dict:
    stars = max(1, min(5, 1 + round(avg_score / 25)))
    labels = {1: "Health-code violation", 2: "Greasy spoon", 3: "Passable bistro",
              4: "Solid brigade", 5: "Michelin-grade prompting"}
    return {"stars": stars, "label": labels[stars]}


def _tokens_saved_estimate() -> int:
    """Rough estimate (~4 chars/token) of tokens Gordon saved by flagging bloated
    prompts: the gap between what the user sent and the tighter rewrite. Labeled
    an estimate everywhere it is shown — no invented statistics (PRD section 8)."""
    rows = db.rows("""
        SELECT e.prompt_text, ev.improved_prompt
        FROM evaluations ev JOIN events e USING(event_id)
        WHERE ev.severity >= 1
          AND json_extract(ev.category_scores, '$.token_conservation') < 60
    """)
    saved = 0
    for r in rows:
        saved += max(0, (len(r["prompt_text"] or "") - len(r["improved_prompt"] or "")) // 4)
    return saved


def category_averages() -> dict[str, float | None]:
    rows = db.rows("SELECT category_scores FROM evaluations")
    sums = {c: [0, 0] for c in CATEGORIES}
    for r in rows:
        for cat, score in json.loads(r["category_scores"]).items():
            if cat in sums:
                sums[cat][0] += score
                sums[cat][1] += 1
    return {c: round(s / n, 1) if n else None for c, (s, n) in sums.items()}


def summary() -> dict:
    total = db.one("SELECT COUNT(*) n FROM evaluations WHERE severity >= 1")["n"]
    today = db.one("SELECT COUNT(*) n FROM evaluations WHERE severity >= 1 "
                   "AND date(created_at) = date('now')")["n"]
    yesterday = db.one("SELECT COUNT(*) n FROM evaluations WHERE severity >= 1 "
                       "AND date(created_at) = date('now','-1 day')")["n"]
    avg = db.one("SELECT AVG(overall_score) a FROM evaluations")["a"]
    common = db.one("SELECT primary_category c, COUNT(*) n FROM evaluations "
                    "WHERE severity >= 1 GROUP BY primary_category ORDER BY n DESC LIMIT 1")
    cat_avgs = category_averages()
    scored = {c: v for c, v in cat_avgs.items() if v is not None}
    best = max(scored, key=scored.get) if scored else None
    worst = min(scored, key=scored.get) if scored else None

    return {
        "total_interruptions": total,
        "interruptions_today": today,
        "interruptions_yesterday": yesterday,
        "average_prompt_score": round(avg, 1) if avg is not None else None,
        "tokens_potentially_saved_estimate": _tokens_saved_estimate(),
        "most_common_mistake": CATEGORY_LABELS.get(common["c"]) if common else None,
        "best_category": CATEGORY_LABELS.get(best) if best else None,
        "worst_category": CATEGORY_LABELS.get(worst) if worst else None,
        "kitchen_rating": _kitchen_rating(avg) if avg is not None else None,
        "category_averages": cat_avgs,
    }


def history(days: int = 7) -> list[dict]:
    """Daily series for the improvement-over-time chart."""
    return db.rows("""
        SELECT date(created_at) AS day,
               COUNT(*) AS prompts,
               SUM(CASE WHEN severity >= 1 THEN 1 ELSE 0 END) AS interruptions,
               ROUND(AVG(overall_score), 1) AS average_score
        FROM evaluations
        WHERE created_at >= datetime('now', ?)
        GROUP BY day ORDER BY day
    """, (f"-{days} days",))


def daily_summary() -> dict:
    """The 'you were yelled at 11 times today' text block."""
    today_rows = db.rows("""
        SELECT primary_category, COUNT(*) n FROM evaluations
        WHERE severity >= 1 AND date(created_at) = date('now')
        GROUP BY primary_category ORDER BY n DESC
    """)
    today = sum(r["n"] for r in today_rows)
    yesterday = db.one("SELECT COUNT(*) n FROM evaluations WHERE severity >= 1 "
                       "AND date(created_at) = date('now','-1 day')")["n"]
    lines = [f"You were yelled at {today} time{'s' if today != 1 else ''} today."]
    for r in today_rows:
        lines.append(f"  {r['n']} × {CATEGORY_LABELS.get(r['primary_category'], r['primary_category'])}")
    if yesterday > today and today > 0:
        lines.append(f"Yesterday Gordon yelled at you {yesterday} times. Unfortunately, this counts as progress.")
    return {"today": today, "yesterday": yesterday,
            "by_category": {r["primary_category"]: r["n"] for r in today_rows},
            "text": "\n".join(lines)}
