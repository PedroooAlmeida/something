"""Frontier-knowledge service (PRD section 12): seeded entries + one RSS/Atom
importer to prove the ingestion pipeline is modular."""
import json
import os
import urllib.request
import xml.etree.ElementTree as ET

from . import db

SEED_PATH = os.path.join(os.path.dirname(__file__), "..", "seed", "knowledge_seed.json")

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def seed_if_empty():
    count = db.one("SELECT COUNT(*) n FROM knowledge_updates")["n"]
    if count:
        return 0
    with open(SEED_PATH) as f:
        entries = json.load(f)
    for e in entries:
        db.execute(
            "INSERT INTO knowledge_updates(product, what_changed, release_date, source, "
            "previous_option, new_option, why_it_matters, confidence, imported_from) "
            "VALUES(?,?,?,?,?,?,?,?, 'seed')",
            (e["product"], e["what_changed"], e.get("release_date"), e.get("source"),
             e.get("previous_option"), e.get("new_option"), e.get("why_it_matters"),
             e.get("confidence", "seeded-demo")),
        )
    return len(entries)


def _text(el, tag_rss, tag_atom):
    child = el.find(tag_rss)
    if child is None:
        child = el.find(ATOM_NS + tag_atom)
    return (child.text or "").strip() if child is not None and child.text else ""


def _link(el):
    link = el.find("link")
    if link is not None and link.text:
        return link.text.strip()
    for a in el.findall(ATOM_NS + "link"):
        if a.get("rel") in (None, "alternate"):
            return a.get("href", "")
    return ""


def import_feed(url: str, product: str | None = None, limit: int = 10) -> dict:
    """Import an RSS 2.0 or Atom feed (e.g. a GitHub releases feed) as knowledge
    updates. Imported entries are marked confidence='unverified' — Gordon only
    states them with source + date attached, never as invented fact."""
    req = urllib.request.Request(url, headers={"User-Agent": "gordon-knowledge/0.1"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        root = ET.fromstring(resp.read())

    if root.tag == ATOM_NS + "feed":
        feed_title = _text(root, "title", "title")
        items = root.findall(ATOM_NS + "entry")
    else:  # RSS 2.0
        channel = root.find("channel")
        feed_title = _text(channel, "title", "title") if channel is not None else ""
        items = channel.findall("item") if channel is not None else []

    imported = 0
    for item in items[:limit]:
        title = _text(item, "title", "title")
        if not title:
            continue
        link = _link(item)
        date = _text(item, "pubDate", "updated") or _text(item, "pubDate", "published")
        exists = db.one("SELECT id FROM knowledge_updates WHERE what_changed=? AND source=?",
                        (title, link))
        if exists:
            continue
        db.execute(
            "INSERT INTO knowledge_updates(product, what_changed, release_date, source, "
            "why_it_matters, confidence, imported_from) VALUES(?,?,?,?,?,?,?)",
            (product or feed_title or "unknown", title, date, link,
             "Imported from release feed — open the source for details.",
             "unverified", url),
        )
        imported += 1
    return {"feed": feed_title, "imported": imported, "seen": len(items)}


def search(q: str | None = None, product: str | None = None) -> list[dict]:
    query = "SELECT * FROM knowledge_updates WHERE 1=1"
    params: list = []
    if product:
        query += " AND product LIKE ?"
        params.append(f"%{product}%")
    if q:
        query += (" AND (what_changed LIKE ? OR previous_option LIKE ? "
                  "OR new_option LIKE ? OR why_it_matters LIKE ?)")
        params += [f"%{q}%"] * 4
    query += " ORDER BY release_date DESC"
    return db.rows(query, tuple(params))
