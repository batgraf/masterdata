# -*- coding: utf-8 -*-
"""
Ładowanie produktów z JSON i XML (mapowanie suuhouse → format wewnętrzny).
"""
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List

from db import PRODUCT_KEYS

# Mapowanie: tag XML suuhouse → klucz wewnętrzny (JSON)
XML_SUUHOUSE_TO_JSON = {
    "Id_produktu": "ID_produktu",
    "Nr_katalogowy": "SKU",
    "Nazwa_produktu": "Nazwa",
    "Kod_ean": "EAN",
    "Producent": "Nazwa_producenta",
    "Waga": "Waga_brutto",
    "Cena_brutto": "Cena_sprzedazy_brutto",
    "Cena_netto": "Cena_sprzedazy_netto",
    "Cena_zakupu": "Cena_zakupu_brutto",
    "Ilosc_produktow": "Stan_magazynowy",
    "Jednostka_miary": "JM_sprzedazy",
    "Dostepnosc": "Dostepnosc",
    "Kategorie_id": "Grupa_produktu",  # uproszczenie: kategorie jako grupa
}


def _text(elem) -> str:
    if elem is None or elem.text is None:
        return ""
    return (elem.text or "").strip()


def _ensure_keys(product: Dict[str, Any]) -> Dict[str, Any]:
    """Uzupełnia brakujące klucze wartością None."""
    for k in PRODUCT_KEYS:
        if k not in product:
            product[k] = None
    return product


def load_from_json_bytes(content: bytes) -> List[Dict[str, Any]]:
    """Wczytuje listę produktów z bajtów JSON. Zwraca listę słowników z kluczami jak w PRODUCT_KEYS."""
    raw = content.decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Oczekiwano listy produktów")
    out = []
    for p in data:
        row = {}
        for k in PRODUCT_KEYS:
            row[k] = p.get(k)
        out.append(_ensure_keys(row))
    return out


def _local_tag(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def load_from_xml_suuhouse(content: bytes) -> List[Dict[str, Any]]:
    """
    Parsuje XML w formacie suuhouse (root Produkty, elementy Produkt).
    Zwraca listę słowników w formacie wewnętrznym (te same klucze co JSON).
    """
    root = ET.fromstring(content)
    out = []
    for elem in root.iter():
        if _local_tag(elem.tag) != "Produkt":
            continue
        row = {k: None for k in PRODUCT_KEYS}
        for child in elem:
            tag = _local_tag(child.tag)
            internal_key = XML_SUUHOUSE_TO_JSON.get(tag)
            if internal_key is None:
                continue
            val = (child.text or "").strip()
            if not val:
                val = None
            if val is not None and internal_key in (
                "ID_produktu", "ID_producenta", "Waga_brutto", "Stan_magazynowy",
                "Cena_sprzedazy_brutto", "Cena_sprzedazy_netto", "Cena_zakupu_brutto",
            ):
                try:
                    val = float(val.replace(",", "."))
                    if internal_key in ("ID_produktu", "ID_producenta"):
                        val = int(val)
                except (ValueError, TypeError):
                    pass
            row[internal_key] = val
        out.append(_ensure_keys(row))
    return out
