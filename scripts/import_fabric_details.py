"""
Importiert Stoffdetails aus einer CSV-Datei in die fabrics-Tabelle.

Die erwartete CSV-Datei liegt standardmäßig unter ``storage/fabrics_export-2.csv``
und verwendet Semikolon (``;``) als Trennzeichen. Wichtige Spalten:
- Stoffcode (Pflicht)
- Stofflieferant
- Herstellungsland
- Lager (Meter, z. B. "213.23 m")
- Bestellte Menge
- Voraussichtliches Empfangsdatum
- Status
- Preiskat
- Zusammensetzung
- Gewicht (z. B. "250 gr/ml")
- Eigenschaften
- Katalog
- Produkttyp
- Stoffart
- Stofffarbe
- Saison
- MTO (Yes/No)

Die Daten werden anhand des ``fabric_code`` (Stoffcode) upserted. Fehlende Felder
in der Datenbank werden ergänzt, vorhandene Werte werden nicht überschrieben.
Zusätzliche Informationen landen in ``additional_metadata``.

Beispiel:
    python scripts/import_fabric_details.py \
        --source storage/fabrics_export-2.csv

Optionaler Dry-Run (kein DB-Zugriff nötig):
    python scripts/import_fabric_details.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import asyncpg
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4


def parse_weight(raw_weight: Optional[str]) -> Optional[int]:
    """Convert weight strings like "250 gr/ml" to integer grams."""
    if not raw_weight:
        return None

    match = re.search(r"(\d+)", str(raw_weight))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def parse_meter_value(raw_value: Optional[str]) -> Optional[float]:
    """Extract meter information from strings like "213.23 m"."""
    if not raw_value:
        return None

    match = re.search(r"([0-9]+(?:[.,][0-9]+)?)", str(raw_value))
    if not match:
        return None

    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def normalize_stock_status(stock_meters: Optional[float], status_raw: Optional[str]) -> Optional[str]:
    """Derive a stock status based on inventory and status text."""
    if stock_meters is not None:
        return "in_stock" if stock_meters > 0 else "on_order"

    if status_raw:
        normalized = status_raw.strip().lower().replace(" ", "_")
        return normalized or None

    return None


def normalize_season(raw_season: Optional[str]) -> Optional[str]:
    """Normalize season strings to internal keywords."""
    if not raw_season:
        return None

    value = raw_season.strip().lower()
    if "4" in value or "vier" in value:
        return "4season"
    if "sommer" in value:
        return "summer"
    if "winter" in value:
        return "winter"
    if "herbst" in value:
        return "winter"  # Autumn/Winter collection
    if "frühling" in value or "spring" in value:
        return "summer"
    return value


def parse_expected_date(raw_date: Optional[str]) -> Optional[str]:
    """Parse dates like "23/12/2025" into ISO format."""
    if not raw_date:
        return None

    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw_date.strip(), fmt)
            return dt.date().isoformat()
        except ValueError:
            continue
    return None


def read_csv_rows(csv_path: Path) -> list[Dict[str, str]]:
    """Load all rows from the semicolon-separated CSV."""
    with open(csv_path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        return [row for row in reader if any(row.values())]


def build_fabric_payload(row: Dict[str, str]) -> Dict[str, object]:
    """Map a CSV row to database fields and metadata."""
    fabric_code = (row.get("Stoffcode") or "").strip()
    supplier = (row.get("Stofflieferant") or "").strip() or None
    origin = (row.get("Herstellungsland") or "").strip() or None
    stock_meters = parse_meter_value(row.get("Lager"))
    ordered_meters = parse_meter_value(row.get("Bestellte Menge"))
    expected_delivery = parse_expected_date(row.get("Voraussichtliches Empfangsdatum"))
    status_raw = (row.get("Status") or "").strip() or None
    weight = parse_weight(row.get("Gewicht"))
    price_category = (row.get("Preiskat") or "").strip() or None
    category = (row.get("Produkttyp") or "").strip() or None
    pattern = (row.get("Stoffart") or row.get("Eigenschaften") or "").strip() or None
    color = (row.get("Stofffarbe") or "").strip() or None
    season = normalize_season(row.get("Saison"))

    additional_metadata = {
        "catalog": row.get("Katalog"),
        "fabric_type": row.get("Stoffart"),
        "properties": row.get("Eigenschaften"),
        "product_type": category,
        "season_raw": row.get("Saison"),
        "season": season,
        "mto": row.get("MTO"),
        "ordered_meters": ordered_meters,
        "stock_meters": stock_meters,
        "expected_delivery": expected_delivery,
        "status_raw": status_raw,
        "price_category_raw": price_category,
    }

    # Remove None values from metadata
    additional_metadata = {k: v for k, v in additional_metadata.items() if v is not None}

    stock_status = normalize_stock_status(stock_meters, status_raw)

    name_parts = [part for part in (supplier, fabric_code) if part]
    name = " ".join(name_parts) if name_parts else f"Stoff {fabric_code or 'unbekannt'}"

    return {
        "id": str(uuid4()),
        "fabric_code": fabric_code,
        "name": name,
        "supplier": supplier,
        "composition": (row.get("Zusammensetzung") or "").strip() or None,
        "weight": weight,
        "color": color,
        "pattern": pattern,
        "category": category,
        "price_category": price_category,
        "origin": origin,
        "stock_status": stock_status,
        "metadata": additional_metadata,
    }


async def upsert_fabric(conn: asyncpg.Connection, payload: Dict[str, object]) -> str:
    """Insert or update a single fabric record."""
    existing = await conn.fetchrow(
        "SELECT id FROM fabrics WHERE fabric_code = $1", payload["fabric_code"]
    )

    if existing:
        await conn.execute(
            """
            UPDATE fabrics
            SET
                supplier = COALESCE($2, supplier),
                composition = COALESCE($3, composition),
                weight = COALESCE($4, weight),
                color = COALESCE($5, color),
                pattern = COALESCE($6, pattern),
                category = COALESCE($7, category),
                price_category = COALESCE($8, price_category),
                origin = COALESCE($9, origin),
                stock_status = COALESCE($10, stock_status),
                additional_metadata = COALESCE(additional_metadata, '{}'::jsonb) || $11::jsonb,
                updated_at = NOW()
            WHERE id = $1
            """,
            existing["id"],
            payload["supplier"],
            payload["composition"],
            payload["weight"],
            payload["color"],
            payload["pattern"],
            payload["category"],
            payload["price_category"],
            payload["origin"],
            payload["stock_status"],
            json.dumps(payload["metadata"]),
        )
        return "updated"

    await conn.execute(
        """
        INSERT INTO fabrics (
            id, fabric_code, name, supplier, composition, weight,
            color, pattern, category, price_category,
            origin, stock_status, additional_metadata,
            created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6,
            $7, $8, $9, $10, $11,
            $12, $13, NOW(), NOW()
        )
        """,
        payload["id"],
        payload["fabric_code"],
        payload["name"],
        payload["supplier"],
        payload["composition"],
        payload["weight"],
        payload["color"],
        payload["pattern"],
        payload["category"],
        payload["price_category"],
        payload["origin"],
        payload["stock_status"],
        json.dumps(payload["metadata"]),
    )
    return "inserted"


async def import_fabric_details(csv_path: Path, dry_run: bool = False) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV nicht gefunden: {csv_path}")

    rows = read_csv_rows(csv_path)
    print(f"📂 {len(rows)} Zeilen aus {csv_path} geladen")

    if dry_run:
        preview = [build_fabric_payload(row) for row in rows[:3]]
        print("🧪 Dry-Run aktiviert – keine Datenbankänderungen")
        print(json.dumps(preview, indent=2, ensure_ascii=False))
        return

    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")
    if not db_url:
        raise ValueError("DATABASE_URL oder POSTGRES_CONNECTION_STRING fehlt")

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    print("🔌 Verbinde zur Datenbank …")
    conn = await asyncpg.connect(db_url)

    inserted = 0
    updated = 0
    errors = 0

    try:
        for idx, row in enumerate(rows, start=1):
            payload = build_fabric_payload(row)

            if not payload["fabric_code"]:
                errors += 1
                print(f"⚠️  Zeile {idx} ohne Stoffcode übersprungen")
                continue

            try:
                result = await upsert_fabric(conn, payload)
                if result == "inserted":
                    inserted += 1
                else:
                    updated += 1

                if (inserted + updated) % 100 == 0:
                    print(f"  → {inserted} eingefügt, {updated} aktualisiert …")

            except Exception as exc:  # pragma: no cover - defensive logging
                errors += 1
                print(f"❌ Fehler bei {payload['fabric_code']}: {exc}")

        print("\n✅ Import abgeschlossen")
        print(f"   Neu eingefügt: {inserted}")
        print(f"   Aktualisiert:  {updated}")
        if errors:
            print(f"   Fehler/Übersprungen: {errors}")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Importiert Stoffdetails aus CSV")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("storage/fabrics_export-2.csv"),
        help="Pfad zur CSV-Datei",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parst die CSV und zeigt die ersten Einträge ohne DB-Zugriff",
    )

    args = parser.parse_args()
    asyncio.run(import_fabric_details(args.source, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
