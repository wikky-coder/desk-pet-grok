"""v4-4: festival of the day (Qt-free). Gregorian festivals are fixed; the lunar ones (春节 / 元宵 / 端午 / 中秋) come from a table
for 2025-2045 (computed with the lunardate package, no runtime dependency). Outside the table only the fixed festivals apply.
Decoration: ``head`` = ornament on her head, ``side`` = items next to her feet (left / right)."""
from __future__ import annotations

import datetime as _dt
from typing import Optional

# generated with the lunardate package (2025-2045); 除夕 = the day before 春节
LUNAR = {
    2025: {"cny": "2025-01-29", "lantern": "2025-02-12", "dragon": "2025-05-31", "midautumn": "2025-10-06"},
    2026: {"cny": "2026-02-17", "lantern": "2026-03-03", "dragon": "2026-06-19", "midautumn": "2026-09-25"},
    2027: {"cny": "2027-02-06", "lantern": "2027-02-20", "dragon": "2027-06-09", "midautumn": "2027-09-15"},
    2028: {"cny": "2028-01-26", "lantern": "2028-02-09", "dragon": "2028-05-28", "midautumn": "2028-10-03"},
    2029: {"cny": "2029-02-13", "lantern": "2029-02-27", "dragon": "2029-06-16", "midautumn": "2029-09-22"},
    2030: {"cny": "2030-02-03", "lantern": "2030-02-17", "dragon": "2030-06-05", "midautumn": "2030-09-12"},
    2031: {"cny": "2031-01-23", "lantern": "2031-02-06", "dragon": "2031-06-24", "midautumn": "2031-10-01"},
    2032: {"cny": "2032-02-11", "lantern": "2032-02-25", "dragon": "2032-06-12", "midautumn": "2032-09-19"},
    2033: {"cny": "2033-01-31", "lantern": "2033-02-14", "dragon": "2033-06-01", "midautumn": "2033-09-08"},
    2034: {"cny": "2034-02-19", "lantern": "2034-03-05", "dragon": "2034-06-20", "midautumn": "2034-09-27"},
    2035: {"cny": "2035-02-08", "lantern": "2035-02-22", "dragon": "2035-06-10", "midautumn": "2035-09-16"},
    2036: {"cny": "2036-01-28", "lantern": "2036-02-11", "dragon": "2036-05-30", "midautumn": "2036-10-04"},
    2037: {"cny": "2037-02-15", "lantern": "2037-03-01", "dragon": "2037-06-18", "midautumn": "2037-09-24"},
    2038: {"cny": "2038-02-04", "lantern": "2038-02-18", "dragon": "2038-06-07", "midautumn": "2038-09-13"},
    2039: {"cny": "2039-01-24", "lantern": "2039-02-07", "dragon": "2039-05-27", "midautumn": "2039-10-02"},
    2040: {"cny": "2040-02-12", "lantern": "2040-02-26", "dragon": "2040-06-14", "midautumn": "2040-09-20"},
    2041: {"cny": "2041-02-01", "lantern": "2041-02-15", "dragon": "2041-06-03", "midautumn": "2041-09-10"},
    2042: {"cny": "2042-01-22", "lantern": "2042-02-05", "dragon": "2042-06-22", "midautumn": "2042-09-28"},
    2043: {"cny": "2043-02-10", "lantern": "2043-02-24", "dragon": "2043-06-11", "midautumn": "2043-09-17"},
    2044: {"cny": "2044-01-30", "lantern": "2044-02-13", "dragon": "2044-05-31", "midautumn": "2044-10-05"},
    2045: {"cny": "2045-02-17", "lantern": "2045-03-03", "dragon": "2045-06-19", "midautumn": "2045-09-25"},
}


# key -> (label, head ornament, (left item, right item))
FESTIVALS = {
    "halloween": ("万圣节", "witch", ("pumpkin", None)),
    "christmas": ("圣诞节", "santa", (None, "gingerbread")),
    "newyear": ("元旦", "party", (None, None)),
    "cny": ("春节", "flowers", ("envelope", "lantern")),
    "lantern": ("元宵节", "flowers", ("lantern", "tangyuan")),
    "dragon": ("端午节", None, (None, "zongzi")),
    "midautumn": ("中秋节", None, (None, "mooncake")),
    "national": ("国庆节", None, ("flag", None)),
}


def festival_on(d: _dt.date) -> Optional[str]:
    md = (d.month, d.day)
    if md == (10, 31):
        return "halloween"
    if md in ((12, 24), (12, 25)):
        return "christmas"
    if md == (1, 1):
        return "newyear"
    if md == (10, 1):
        return "national"
    row = LUNAR.get(d.year)
    if row:
        cny = _dt.date.fromisoformat(row["cny"])
        if d in (cny - _dt.timedelta(days=1), cny):  # 除夕 + 初一
            return "cny"
        for key in ("lantern", "dragon", "midautumn"):
            if d.isoformat() == row[key]:
                return key
    return None


def label(key: str) -> str:
    return FESTIVALS[key][0]
