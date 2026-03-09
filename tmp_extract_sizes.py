#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wyłuskuje rozmiary z nazw produktów.
Wzorce: 530x1000mm, 45,2X45,2, 7,5 X 30, 3x4m, 6X3X2,1 M, 283x251 cm, 0,8X1,6M itd.

Użycie:
  ./venv/bin/python tmp_extract_sizes.py          # test na kilku przykładach
  ./venv/bin/python tmp_extract_sizes.py --dry   # pokaż co by zaktualizowano (bez zapisu)
  ./venv/bin/python tmp_extract_sizes.py --do    # zapisz do bazy (Dlugosc, Szerokosc, Wysokosc)
"""
import re
import sys
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


def _to_float(s: str) -> Optional[float]:
    """Konwertuje '45,2' lub '45.2' na float."""
    if not s or not s.strip():
        return None
    s = str(s).strip().replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def extract_sizes(nazwa: str) -> Optional[Dict[str, Any]]:
    """
    Wyłuskuje wymiary z nazwy. Zwraca np.:
    {"Dlugosc": 1000, "Szerokosc": 530, "Wysokosc": None, "JM_wymiaru": "cm"}
    lub {"Dlugosc": 4, "Szerokosc": 3, "Wysokosc": 2.1, "JM_wymiaru": "m"}
    Zwraca None jeśli nic nie znaleziono.
    """
    if not nazwa or not isinstance(nazwa, str):
        return None

    nazwa_upper = nazwa.upper()
    result: Dict[str, Any] = {"Dlugosc": None, "Szerokosc": None, "Wysokosc": None, "JM_wymiaru": "cm"}

    # Jednostka – szukaj mm, cm, m na końcu wzorca
    unit = "cm"  # domyślnie cm (płytki, grzejniki w mm traktujemy jak cm dla Dlugosc/Szerokosc)
    if "MM" in nazwa_upper or "MM)" in nazwa_upper:
        unit = "cm"  # 530x1000mm → zapisuję w cm: 53 x 100 lub zostawiam mm?
    if " M " in nazwa_upper or " M)" in nazwa_upper or "M FOLIA" in nazwa_upper:
        unit = "m"
    # Wzorce typu 3x4m, 6X3X2,1 M
    if re.search(r"\d[\d,\.]*\s*[xX×]\s*\d[\d,\.]*\s*[mM]\b", nazwa):
        unit = "m"
    if re.search(r"\d[\d,\.]*\s*[xX×]\s*\d[\d,\.]*\s*mm", nazwa, re.I):
        unit = "cm"  # mm → w bazie często cm; można zmienić na "mm"

    # Wzorzec: liczba[xX×]liczba  lub  liczba,[liczba][xX×]liczba
    # Obsługa 2 lub 3 wymiarów
    # Wyklucz 5x12W (watty) – wymiary po x nie mogą być < 15 dla formatu W
    pat_2d = re.compile(
        r"(\d[\d,\.]*)\s*[xX×]\s*(\d[\d,\.]*)\s*(?:mm|cm|m|M)?(?![wW])",
        re.I
    )
    pat_3d = re.compile(
        r"(\d[\d,\.]*)\s*[xX×]\s*(\d[\d,\.]*)\s*[xX×]\s*(\d[\d,\.]*)\s*(?:mm|cm|m|M)?",
        re.I
    )
    # Wersja z jednostką na końcu całości: 6X3X2,1 M
    pat_3d_m = re.compile(
        r"(\d[\d,\.]*)\s*[xX×]\s*(\d[\d,\.]*)\s*[xX×]\s*(\d[\d,\.]*)\s*[mM]\b",
        re.I
    )
    # W nawiasie: (530,508, BIAŁY) lub (1,22M)
    pat_bracket = re.compile(r"\((\d[\d,\.]*)\s*[xX,×]\s*(\d[\d,\.]*)\)", re.I)
    pat_bracket_single = re.compile(r"\((\d[\d,\.]*)[mM]\)", re.I)

    vals: List[float] = []

    # Priorytet: 3D z M
    m3 = pat_3d_m.search(nazwa)
    if m3:
        vals = [_to_float(m3.group(1)), _to_float(m3.group(2)), _to_float(m3.group(3))]
        unit = "m"
    if not vals:
        m3b = pat_3d.search(nazwa)
        if m3b:
            vals = [_to_float(m3b.group(1)), _to_float(m3b.group(2)), _to_float(m3b.group(3))]
            if "M " in nazwa_upper or " M)" in nazwa_upper:
                unit = "m"
    if not vals:
        m2 = pat_2d.search(nazwa)
        if m2:
            vals = [_to_float(m2.group(1)), _to_float(m2.group(2))]
    if not vals:
        mb = pat_bracket.search(nazwa)
        if mb:
            vals = [_to_float(mb.group(1)), _to_float(mb.group(2))]
    if not vals:
        ms = pat_bracket_single.search(nazwa)
        if ms:
            vals = [_to_float(ms.group(1))]
            unit = "m"
    if not vals:
        # Pojedynczy wymiar: 40cm, 9 CM
        pat_1d_cm = re.compile(r"(?<!\d)(\d[\d,\.]*)\s*cm\b", re.I)
        pat_1d_m = re.compile(r"(?<!\d)(\d[\d,\.]*)\s*m\b(?!m)", re.I)
        m1cm = pat_1d_cm.search(nazwa)
        m1m = pat_1d_m.search(nazwa)
        if m1cm:
            vals = [_to_float(m1cm.group(1))]
            unit = "cm"
        elif m1m:
            vals = [_to_float(m1m.group(1))]
            unit = "m"

    # Pominij fałszywe trafienia: 5x12W (moc), 2D, 4UV, AC5, LP-005/6P itd.
    def _skip(v: float) -> bool:
        if v is None:
            return True
        if v < 0.1 or v > 10000:
            return True
        return False

    # 5x12W (watty) – pominąć gdy drugi wymiar ≤ 15 i w nazwie jest ...xN W
    if len(vals) == 2 and vals[1] is not None and vals[1] <= 15:
        if re.search(r"\d\s*[xX×]\s*\d+\s*[wW]", nazwa):
            vals = []

    vals = [v for v in vals if v is not None and not _skip(v)]
    if not vals:
        return None

    # Dla wzorców z "mm" – gdy wartości duże (≥100) = wymiary w mm, konwersja na cm
    if "mm" in nazwa.lower() and any(v and v >= 100 for v in vals):
        vals = [round(v / 10.0, 1) if v else v for v in vals]
        unit = "cm"

    # Mapowanie: Dlugosc, Szerokosc, Wysokosc
    # Konwencja: pierwszy wymiar = Dlugosc, drugi = Szerokosc, trzeci = Wysokosc
    # Dla grzejników 530x1000mm: często H x W → Wysokosc x Szerokosc; w bazie Dlugosc/Szerokosc może być dowolna
    if len(vals) >= 3:
        result["Dlugosc"] = round(vals[0], 2)
        result["Szerokosc"] = round(vals[1], 2)
        result["Wysokosc"] = round(vals[2], 2)
    elif len(vals) == 2:
        result["Dlugosc"] = round(vals[0], 2)
        result["Szerokosc"] = round(vals[1], 2)
    else:
        result["Dlugosc"] = round(vals[0], 2)

    result["JM_wymiaru"] = unit
    return result


def _test_examples():
    """Test na przykładowych nazwach."""
    examples = [
        "Grzejnik łazienkowy SOLEN 2 biały 530x1000mm 375W",
        "Panele Podłogowe Dalia Fiori AQUA ZERO 72h Swiss Krono D 4589 AC6 10 mm",
        "HARMONY PASADENA WHITE 7,5 X 30 G1",
        "TUNEL OGRODOWY AW6 6X3X2,1 M FOLIA 4UV",
        "PŁYTKI PERONDA SAVANNAH SILVER 45,2X45,2 G1",
        "Domek narzędziowy metalowy NORDVIC Magni 283x251 cm",
        "Grzejnik elektryczny TRICK Electro czarny 50x120 cm",
        "LAMELE MDF L AKUSTYCZNE NAT OAK 2800X134X18 OP.6",
        "MIRADOR 80 Solid 3x2,4m + Roleta 3m",
        "FOLIA NA POJ. DRZWI TUNELU A,B 0,8X1,6M",
        "Lampa wisząca PASTELO 5 czarna 5x12W G9 Sollux Lighting",  # 5x12W – pominąć
        "Szafka Górna Comad RETRO 40cm 1 Drzwi",
        "MANACOR OCZKO CZARNE 9 CM",
    ]
    print("=== Test ekstrakcji rozmiarów ===\n")
    for n in examples:
        r = extract_sizes(n)
        if r:
            parts = [f"{k}={v}" for k, v in r.items() if v is not None]
            print(f"OK  | {n[:60]}...")
            print(f"    -> {', '.join(parts)}\n")
        else:
            print(f" -- | {n[:60]}...\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--dry", "--do"):
        # Tryb aktualizacji bazy
        from db import get_connection, get_all_products, update_product, PRODUCT_KEYS
        dry = sys.argv[1] == "--dry"
        print("Ładowanie produktów z bazy...")
        with get_connection() as conn:
            products = get_all_products(conn)
        updated = 0
        for p in products:
            pid = p.get("id")
            nazwa = p.get("Nazwa") or ""
            cur_d = p.get("Dlugosc") or 0
            cur_s = p.get("Szerokosc") or 0
            cur_h = p.get("Wysokosc") or 0
            if (cur_d or cur_s or cur_h) and not dry:
                continue  # już ma wymiary – nie nadpisuj (opcjonalnie)
            ext = extract_sizes(nazwa)
            if not ext:
                continue
            changes = []
            for k in ("Dlugosc", "Szerokosc", "Wysokosc", "JM_wymiaru"):
                v = ext.get(k)
                if v is not None and str(v) != str(p.get(k) or ""):
                    changes.append(f"{k}={v}")
            if not changes:
                continue
            if dry:
                print(f"[DRY] id={pid} {nazwa[:50]}... -> {', '.join(changes)}")
                updated += 1
            else:
                with get_connection() as conn:
                    for k, v in ext.items():
                        if v is not None and k in ("Dlugosc", "Szerokosc", "Wysokosc", "JM_wymiaru"):
                            if update_product(conn, pid, k, v):
                                updated += 1
        print(f"\n{'[DRY-RUN] ' if dry else ''}{'Produktów do zaktualizowania' if dry else 'Zaktualizowano produktów/pól'}: {updated}")
    else:
        _test_examples()
