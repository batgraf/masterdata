#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Uzupełnia kolumnę Rodzaj_opakowania według producenta.
Wzór: Bellanti → karton
Użycie: ./venv/bin/python tmp_fill_opakowanie.py
"""
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from db import get_connection

RULES = [
    # (wzorzec w NAZwie produktu (LIKE), wartość opakowania)
    ("%bellanti%", "karton"),
]


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            total = 0
            for name_pattern, value in RULES:
                cur.execute(
                    """
                    UPDATE products
                    SET "Rodzaj_opakowania" = %s
                    WHERE LOWER(TRIM(COALESCE("Nazwa", ''))) LIKE LOWER(%s)
                      AND ("Rodzaj_opakowania" IS NULL OR TRIM(COALESCE("Rodzaj_opakowania", '')) = '')
                    """,
                    (value, name_pattern),
                )
                n = cur.rowcount
                total += n
                print(f"Zaktualizowano {n} (producent → {value})")
    print(f"Razem: {total} rekordów")


if __name__ == "__main__":
    main()
