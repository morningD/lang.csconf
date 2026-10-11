#!/usr/bin/env python3
"""i18n regression guard for the Finances feature.

Data-driven UI strings (officer titles, expense categories, countries, scopes)
must be covered by the four locale files. This script re-derives the mapping
tables from FinancesView.vue source (single source of truth — no duplicated
tables here) and simulates the translation of every title/value found in the
data files, then checks the locale files for missing keys or locale drift.

Usage: python3 scripts/check_i18n.py   (exit 1 on any violation)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VUE = ROOT / "website/src/views/FinancesView.vue"
LOCALES = {loc: json.load(open(ROOT / f"website/src/i18n/locales/{loc}.json")) for loc in ("en", "zh", "ja", "de")}
FINANCES_STATS = ROOT / "data/stats/finances.json"
DEEP_DIR = ROOT / "data/raw/finances/deep"

problems: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)


# ---- parse TITLE_MAP / ROLE_PHRASES out of the Vue source --------------------
vue_src = VUE.read_text()

m = re.search(r"const TITLE_MAP: Record<string, string> = \{(.*?)\n\}", vue_src, re.S)
if not m:
    fail("FinancesView.vue: cannot locate TITLE_MAP")
    title_map: dict[str, str] = {}
else:
    title_map = {}
    for bare, quoted, val in re.findall(r"(?:'([^']+)'|([A-Za-z0-9_./-]+)):\s*'([^']+)'", m.group(1)):
        title_map[(bare or quoted).strip()] = val.strip()

m = re.search(r"const ROLE_PHRASES: \[string, string\]\[\] = \[(.*?)\n\]", vue_src, re.S)
if not m:
    fail("FinancesView.vue: cannot locate ROLE_PHRASES")
    role_phrases: list[tuple[str, str]] = []
else:
    role_phrases = [(k.strip().strip("'\""), v.strip())
                    for k, v in re.findall(r"\[\s*'([^']+)'\s*,\s*'([^']+)'\s*\]", m.group(1))]

# English role words that must never survive translation of a title's core part
ROLE_WORD_RX = re.compile(r"\b(Chair|Member|President|Treasurer|Secretary|Trustee|Director|Advisor|Manager|Counsel|Volunteer)\b")


def t(loc: str, key: str) -> str:
    node: dict = LOCALES[loc]
    for part in key.split("."):
        node = node.get(part, {})
    return node if isinstance(node, str) else ""


def te(loc: str, key: str) -> bool:
    return bool(t(loc, key))


def localize_title(title: str, loc: str) -> str:
    """Mirror FinancesView.vue officerTitleOf(): exact map → longest-phrase replace."""
    raw = title.strip()
    core, paren = raw, ""
    pm = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", raw)
    if pm and pm[1]:
        core, paren = pm[1].strip(), f" ({pm[2]})"
    mapped = title_map.get(core.lower())
    if mapped and te(loc, f"finances.entity_titles.{mapped}"):
        return t(loc, f"finances.entity_titles.{mapped}") + paren
    out = core
    for phrase, key in role_phrases:
        rk = f"finances.entity_roles.{key}"
        if te(loc, rk) and re.search(re.escape(phrase), out, re.I):
            out = re.sub(re.escape(phrase), t(loc, rk), out, count=1, flags=re.I)
    return out + paren


# ---- 1. locale files must have identical key trees ---------------------------
def key_tree(node, prefix=""):
    keys = set()
    for k, v in node.items():
        p = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= key_tree(v, p)
        else:
            keys.add(p)
    return keys


base_keys = key_tree(LOCALES["en"])
for loc in ("zh", "ja", "de"):
    diff = base_keys.symmetric_difference(key_tree(LOCALES[loc]))
    for k in sorted(diff):
        fail(f"locale drift: key '{k}' {'missing' if k in base_keys else 'extra'} in {loc}.json")

# ---- 2. collect all data-driven values --------------------------------------
titles: Counter = Counter()
mix_keys: set[str] = set()
countries: set[str] = set()
scopes: set[str] = set()

if FINANCES_STATS.exists():
    stats = json.load(open(FINANCES_STATS))
    for conf, entry in stats.get("conferences", {}).items():
        scopes.add(entry.get("scope", ""))
        for y, yd in (entry.get("years") or {}).items():
            for k in (yd.get("expense_mix") or {}):
                mix_keys.add(k)
            for k in (yd.get("revenue_mix") or {}):
                mix_keys.add(k)
        ent = entry.get("entity") or {}
        for o in ent.get("officers") or []:
            titles[o.get("title", "")] += 1
        for m_ in (ent.get("board") or {}).get("members", []):
            titles[m_.get("title", "")] += 1
        for c in (ent.get("committee") or {}).values():
            if isinstance(c, dict):
                for m_ in c.get("members", []):
                    titles[m_.get("title", "")] += 1
        for e in ent.get("top_employees") or []:
            titles[e.get("title", "")] += 1
else:
    fail("data/stats/finances.json missing — run step4 first")

if DEEP_DIR.exists():
    for p in DEEP_DIR.glob("*.json"):
        d = json.load(open(p))
        for o in d.get("officers") or []:
            titles[o.get("title", "")] += 1
        for m_ in (d.get("board") or {}).get("members", []) if isinstance(d.get("board"), dict) else []:
            titles[m_.get("title", "")] += 1
        for c in (d.get("committee") or {}).values():
            if isinstance(c, dict):
                for m_ in c.get("members", []):
                    titles[m_.get("title", "")] += 1
        for e in d.get("top_employees") or []:
            titles[e.get("title", "")] += 1
        for k in d.get("expense_mix") or {}:
            mix_keys.add(k)
        for k in d.get("revenue_mix") or {}:
            mix_keys.add(k)
        for o in d.get("officers") or []:
            if o.get("country"):
                countries.add(o["country"])

# ---- 3. mix keys must be localized ------------------------------------------
for k in sorted(mix_keys):
    for loc in ("en", "zh", "ja", "de"):
        if not te(loc, f"finances.mix_categories.{k}"):
            fail(f"mix key '{k}' missing finances.mix_categories in {loc}.json")
        if not te(loc, f"finances.mix_desc.{k}"):
            fail(f"mix key '{k}' missing finances.mix_desc in {loc}.json")

# ---- 4. every title must survive translation without English role words -----
for title in sorted(titles):
    for loc in ("zh", "ja"):  # en/de legitimately keep some English forms
        out = localize_title(title, loc)
        # trailing "(context)" parentheses are kept verbatim by design — check the core only
        core = re.sub(r"\s*\([^)]*\)\s*$", "", out)
        if ROLE_WORD_RX.search(core):
            fail(f"title {title!r} → {loc}: '{core}' still contains untranslated role words")

# ---- 5. countries and scopes -------------------------------------------------
for c in sorted(countries):
    for loc in ("en", "zh", "ja", "de"):
        if not te(loc, f"finances.country.{c}"):
            fail(f"country code '{c}' missing finances.country in {loc}.json")

scope_keys = set(LOCALES["en"].get("finances", {}).get("scope", {}))
for s in sorted(scopes - {""}):
    if s not in scope_keys:
        fail(f"scope '{s}' missing finances.scope in locale files")

# ---- report ------------------------------------------------------------------
if problems:
    print(f"i18n check FAILED — {len(problems)} problem(s):")
    for p in problems:
        print("  ✗", p)
    sys.exit(1)

n_titles = sum(titles.values())
print(f"i18n check OK: {len(mix_keys)} mix keys, {n_titles} title occurrences "
      f"({len(titles)} distinct), {len(countries)} countries, {len(scopes)} scopes — 4 locales in sync")
