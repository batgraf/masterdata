#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eksportuje produkty z PostgreSQL do AsortymentyMasterData.json.
Użycie: ./venv/bin/python tmp_export_db_to_json.py
"""
from pathlib import Path
import json

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from db import get_connection, get_all_products, PRODUCT_KEYS

OUTPUT_FILE = Path(__file__).resolve().parent / "AsortymentyMasterData.json"


def main():
    with get_connection() as conn:
        products = get_all_products(conn)
    export_list = [{k: p.get(k) for k in PRODUCT_KEYS} for p in products]
    OUTPUT_FILE.write_text(json.dumps(export_list, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Zapisano {len(export_list)} produktów do {OUTPUT_FILE.name}")


if __name__ == "__main__":
    main()
