# -*- coding: utf-8 -*-
"""
Czyta instl_calosc.xlsx (arkusz 'Stan magazynowy') i zapisuje listę produktów
z polami: indeks, EAN, Nazwa, Szerokosc_mm, Wysokosc_mm, Glebokosc_mm, Waga_kg.
Użycie: python scripts/instl_calosc_to_list.py [ścieżka do xlsx] [--output plik.json]
Domyślnie: czyta z BAZY_Producent/instl_calosc.xlsx, zapisuje instl_lista.json w katalogu skryptu.
"""
import json
import os
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("Zainstaluj: pip install pandas openpyxl")
    sys.exit(1)

# Mapowanie kolumn w arkuszu 'Stan magazynowy' (wiersz 1 = nagłówki, dane od wiersza 2)
NAZWA = 3
INDEKS = 4
NAZWA_PELNA = 5
SZEROKOSC = 14
WYSOKOSC = 15
GLEBOKOSC = 16
WAGA = 17
EAN = 26


def _norm(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return s if s else None


def _num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def load_instl_calosc(path: str):
    df = pd.read_excel(path, sheet_name="Stan magazynowy", header=None)
    rows = []
    for i in range(2, len(df)):
        row = df.iloc[i]
        indeks = _norm(row[INDEKS])
        ean = _norm(row[EAN])
        nazwa = _norm(row[NAZWA]) or _norm(row[NAZWA_PELNA])
        szer = _num(row[SZEROKOSC])
        wys = _num(row[WYSOKOSC])
        gleb = _num(row[GLEBOKOSC])
        waga = _num(row[WAGA])
        # Pomijaj wiersze bez indeksu (np. podnagłówki)
        if not indeks:
            continue
        rows.append({
            "indeks": indeks,
            "EAN": ean,
            "Nazwa": nazwa,
            "Szerokosc_mm": szer,
            "Wysokosc_mm": wys,
            "Glebokosc_mm": gleb,
            "Waga_kg": waga,
            "Wymiary": f"{szer or ''} x {wys or ''} x {gleb or ''}".strip(" x") if (szer or wys or gleb) else None,
        })
    return rows


def main():
    script_dir = Path(__file__).resolve().parent
    base = script_dir.parent
    default_path = base / ".." / "BAZY_Producent" / "instl_calosc.xlsx"
    default_path = default_path.resolve()

    path = default_path
    out_path = script_dir / "instl_lista.json"
    args = sys.argv[1:]
    if args and not args[0].startswith("-"):
        path = Path(args[0]).resolve()
        args = args[1:]
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            out_path = Path(args[idx + 1])

    if not path.exists():
        print("Brak pliku:", path)
        sys.exit(1)

    rows = load_instl_calosc(str(path))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("Zapisano", len(rows), "pozycji do", out_path)
    with_ean = sum(1 for r in rows if r.get("EAN"))
    print("Z EAN:", with_ean)


if __name__ == "__main__":
    main()
