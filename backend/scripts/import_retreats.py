#!/usr/bin/env python
"""
Import retreats from data/retreats.csv into the experiences table.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import models
from backend.database import SessionLocal  # noqa: E402

DATA_KEYS = [
    "name",
    "website",
    "location",
    "what_is_it",
    "types",
    "fallback_types",
    "accommodation",
    "diagnostics",
    "focus",
    "duration",
    "price",
    "membership_link",
]

RETREAT_IMAGES = [
    "https://images.unsplash.com/photo-1506126613408-eca07ce68773?q=80&w=2599&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?q=80&w=2720&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1575052814086-f385e2e2ad1b?q=80&w=2670&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1475924156734-496f6cac6ec1?q=80&w=2670&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?q=80&w=2621&auto=format&fit=crop",
]


def clean_cell(value: str) -> str:
    return value.replace('"', "").strip()


def ensure_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://{value.lstrip('/')}"


def split_focus(value: str | None) -> List[str]:
    if not value:
        return []
    return [segment.strip() for segment in value.split(",") if segment.strip()]


def parse_location(raw: str | None) -> Dict[str, str]:
    if not raw:
        return {"city": "Global", "country": "Various"}
    parts = [p.strip() for p in clean_cell(raw).split(",") if p.strip()]
    if not parts:
        return {"city": "Global", "country": "Various"}
    if len(parts) == 1:
        return {"city": parts[0], "country": "Various"}
    return {"city": parts[0], "country": parts[-1]}


def parse_retreat_rows(csv_text: str) -> List[Dict[str, str]]:
    lines = csv_text.replace("\r", "").split("\n")
    rows: List[List[str]] = []
    current_row: List[str] | None = None
    cursor = 0

    def start_row() -> None:
        nonlocal current_row, cursor
        current_row = [""] * len(DATA_KEYS)
        cursor = 0

    def push_row() -> None:
        if current_row and any(cell.strip() for cell in current_row):
            rows.append(current_row)
        start_row()

    start_row()
    for raw_line in lines[1:]:
        if not raw_line.strip():
            continue
        cells = raw_line.split("\t")
        first_cell = clean_cell(cells[0]) if cells else ""
        if first_cell and cursor > 0:
            push_row()
        elif current_row is None:
            start_row()

        for cell in cells:
            value = clean_cell(cell)
            if not value or current_row is None:
                continue
            target = cursor if cursor < len(DATA_KEYS) else len(DATA_KEYS) - 1
            current_row[target] = (
                f"{current_row[target]} {value}".strip()
                if current_row[target]
                else value
            )
            if cursor < len(DATA_KEYS):
                cursor += 1

    if current_row and any(cell.strip() for cell in current_row):
        rows.append(current_row)

    records: List[Dict[str, str]] = []
    for row in rows:
        record = {DATA_KEYS[idx]: row[idx].strip() for idx in range(len(DATA_KEYS))}
        records.append(record)
    return records


def upsert_retreats_from_csv(session) -> int:
    csv_path = PROJECT_ROOT / "data" / "retreats.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Cannot locate {csv_path}")

    csv_text = csv_path.read_text(encoding="utf-8")
    records = parse_retreat_rows(csv_text)
    today = date.today()

    for idx, record in enumerate(records):
        experience_id = f"retreat-csv-{idx}"
        dates_offset = idx % 30
        start_date = (today + timedelta(days=7 + dates_offset)).isoformat()
        end_date = (today + timedelta(days=14 + dates_offset)).isoformat()
        location = parse_location(record.get("location"))

        amenities = [
            value
            for value in [
                record.get("accommodation"),
                record.get("diagnostics"),
                record.get("price"),
            ]
            if value
        ]

        data = {
            "type": "retreat",
            "name": record.get("name"),
            "theme": record.get("types")
            or record.get("what_is_it")
            or "Wellness Retreat",
            "mission": record.get("what_is_it")
            or record.get("duration")
            or "Curated retreat experience.",
            "curator_id": "retreat-importer",
            "start_date": start_date,
            "end_date": end_date,
            "image": RETREAT_IMAGES[idx % len(RETREAT_IMAGES)],
            "price_usd": None,
            "website": ensure_url(record.get("website")),
            "membership_link": ensure_url(record.get("membership_link")),
            "city": location["city"],
            "country": location["country"],
            "price_label": record.get("price"),
            "duration_label": record.get("duration"),
            "listing_ids": [],
            "amenities": amenities,
            "activities": split_focus(record.get("focus")),
        }

        db_experience = (
            session.query(models.Experience)
            .filter(models.Experience.id == experience_id)
            .first()
        )
        if db_experience:
            for field, value in data.items():
                setattr(db_experience, field, value)
        else:
            session.add(models.Experience(id=experience_id, **data))

    session.commit()
    return len(records)


def main() -> None:
    session = SessionLocal()
    try:
        count = upsert_retreats_from_csv(session)
        print(f"Imported/updated {count} retreats from data/retreats.csv")
    finally:
        session.close()


if __name__ == "__main__":
    main()
