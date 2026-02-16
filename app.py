import json
import shutil
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Załaduj .env (DATABASE_URL) przed importem db
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from flask import Flask, render_template, request, jsonify, send_file
import subprocess

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "AsortymentyMasterData.json"
VIEWS_DIR = BASE_DIR / "column_views"
STATS_FILE = BASE_DIR / "stats.json"
VERSION_FILE = BASE_DIR / "VERSION.txt"

app = Flask(__name__)
# Zwiększ limit uploadu do 50MB (domyślnie Flask ma 16MB)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
_DATA_CACHE: Dict[str, Any] = {"mtime": None, "products": []}

# PostgreSQL – gdy ustawiony DATABASE_URL, dane z bazy zamiast z pliku
try:
    from db import (
    get_database_url, get_connection, init_db, ensure_extra_tables,
    get_all_products, insert_products,
    update_product as db_update_product, delete_products_by_ids,
    batch_update_products as db_batch_update_products, clear_products,
    save_user_base, list_user_bases, get_user_base,
    create_system_backup, restore_from_latest_backup, get_product,
    get_products_id_produktu, insert_change_log, get_changes_since, get_change_log_grouped,
    PRODUCT_KEYS, NUMERIC_KEYS as DB_NUMERIC_KEYS,
)
    from data_loaders import load_from_json_bytes, load_from_xml_suuhouse
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False
    PRODUCT_KEYS = [
        "ID_produktu", "Tryb", "Status_produktu", "SKU", "Nazwa", "URL_Miniatura",
        "Rodzaj_produktu", "Grupa_produktu", "EAN", "JM_sprzedazy", "Waga_brutto",
        "JM_wagi", "Dlugosc", "Szerokosc", "Wysokosc", "JM_wymiaru",
        "Objetosc_produktu", "JM_objetosci", "Rodzaj_opakowania", "ID_producenta",
        "Nazwa_producenta", "Cena_zakupu_netto", "Cena_zakupu_brutto", "Waluta_zakupu",
        "Nazwa_Cennika", "Cena_sprzedazy_netto", "Cena_sprzedazy_brutto", "Waluta_sprzedazy",
        "Stan_magazynowy", "Rezerwacja", "Dostepnosc",
    ]
    DB_NUMERIC_KEYS = {"ID_produktu", "ID_producenta", "Waga_brutto", "Dlugosc", "Szerokosc", "Wysokosc", "Objetosc_produktu", "Cena_zakupu_netto", "Cena_zakupu_brutto", "Cena_sprzedazy_netto", "Cena_sprzedazy_brutto", "Stan_magazynowy", "Rezerwacja"}

def _use_db() -> bool:
    if not _DB_AVAILABLE:
        return False
    return bool(get_database_url())


def _norm(v) -> str:
    """Wartość do porównania (string, pusty gdy None)."""
    if v is None:
        return ""
    return str(v).strip()


def _products_match(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Czy dwa rekordy to ten sam produkt (ID, SKU lub EAN)."""
    id_a, id_b = _norm(a.get("ID_produktu")), _norm(b.get("ID_produktu"))
    if id_a and id_b and id_a == id_b:
        return True
    sku_a, sku_b = _norm(a.get("SKU")), _norm(b.get("SKU"))
    if sku_a and sku_b and sku_a == sku_b:
        return True
    ean_a, ean_b = _norm(a.get("EAN")), _norm(b.get("EAN"))
    if ean_a and ean_b and ean_a == ean_b:
        return True
    return False


def _merge_products(existing: List[Dict[str, Any]], new_list: List[Dict[str, Any]], new_is_master: bool = True) -> List[Dict[str, Any]]:
    """
    Scala existing z new_list. new_is_master=True: przy konflikcie wygrywa new.
    Dopasowanie po ID, SKU lub EAN. Dopasowana para → jeden rekord (master + uzupełnienie pustych z drugiego).
    """
    result: List[Dict[str, Any]] = []
    used_existing = [False] * len(existing)
    for new_p in new_list:
        merged = dict(new_p)
        match_idx = None
        for i, ex in enumerate(existing):
            if used_existing[i]:
                continue
            if _products_match(ex, new_p):
                match_idx = i
                break
        if match_idx is not None:
            used_existing[match_idx] = True
            ex = existing[match_idx]
            for k in PRODUCT_KEYS:
                if k not in merged:
                    merged[k] = ex.get(k)
                else:
                    val = merged.get(k)
                    if val is None or (isinstance(val, str) and val.strip() == ""):
                        merged[k] = ex.get(k)
        result.append(merged)
    for i, ex in enumerate(existing):
        if not used_existing[i]:
            result.append(dict(ex))
    return result


if _use_db():
    try:
        init_db()
    except Exception:
        pass  # Tabela powstanie przy pierwszym użyciu lub przy ręcznym uruchomieniu

# Import history manager
try:
    from history_manager import (
        save_snapshot,
        load_snapshot,
        get_history_list,
        clear_history,
    )
    HISTORY_ENABLED = True
except ImportError:
    HISTORY_ENABLED = False


@app.template_filter("fmt_num")
def fmt_num(value):
    """
    Formatowanie liczb:
    - jeśli None lub puste -> pusty string,
    - jeśli liczba całkowita typu 40.0 -> '40',
    - w pozostałych przypadkach zwraca oryginalną wartość.
    """
    if value is None:
        return ""
    try:
        # Jeśli da się zrzutować na float i jest całkowite -> bez części dziesiętnej
        f = float(value)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except (ValueError, TypeError):
        return value


@app.template_filter("producer_short")
def producer_short(name: str):
    """
    Skraca długą nazwę SALAG do 'SALAG',
    a 'CERAMIKA ILONA PIETRZAK' do 'Ceramika'.
    """
    if not name:
        return name
    if not isinstance(name, str):
        return name
    upper = name.strip().upper()
    if upper == "SALAG SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ":
        return "SALAG"
    if upper == "CERAMIKA ILONA PIETRZAK":
        return "Ceramika"
    return name


def load_products():
    """Wczytuje listę produktów z pliku JSON lub z bazy (gdy DATABASE_URL)."""
    if _use_db():
        with get_connection() as conn:
            return get_all_products(conn)
    mtime = DATA_FILE.stat().st_mtime
    if _DATA_CACHE["mtime"] == mtime and _DATA_CACHE["products"]:
        return _DATA_CACHE["products"]
    raw = DATA_FILE.read_text(encoding="utf-8")
    data = json.loads(raw)
    _DATA_CACHE["mtime"] = mtime
    _DATA_CACHE["products"] = data
    return data


def is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def is_missing_weight(value: Any) -> bool:
    if is_missing(value):
        return True
    try:
        return float(value) == 0
    except (ValueError, TypeError):
        return False


def is_column_empty(product: Dict[str, Any], column_key: str) -> bool:
    """Wartość pusta: None, '', 0, 0.0, tekst '0'. Dla Waga_brutto używamy is_missing_weight."""
    val = product.get(column_key)
    if column_key == "Waga_brutto":
        return is_missing_weight(val)
    if val is None:
        return True
    if isinstance(val, str):
        return val.strip() == "" or val.strip() == "0"
    try:
        return float(val) == 0
    except (ValueError, TypeError):
        return False


def producer_short_value(name: Any) -> Any:
    if not name or not isinstance(name, str):
        return name
    upper = name.strip().upper()
    if upper == "SALAG SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ":
        return "SALAG"
    if upper == "CERAMIKA ILONA PIETRZAK":
        return "Ceramika"
    return name


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_for_search(text: str) -> str:
    """Usuwa spacje, do dopasowania fraz (np. '3 x 4' = '3x4')."""
    if not text or not isinstance(text, str):
        return ""
    return "".join(text.split()).lower()


def _product_matches_search(product: Dict[str, Any], query: str) -> bool:
    """
    Sprawdza, czy produkt pasuje do frazy wyszukiwania.
    Nazwa jest przeszukiwana; fraza jest dzielona na tokeny (spacje);
    każdy token po normalizacji (bez spacji) musi wystąpić w znormalizowanej nazwie.
    Np. 'pergola 3x4' lub '3 x 4' znajdzie 'pergola skyline 3x4'.
    """
    if not query or not query.strip():
        return True
    name = str(product.get("Nazwa") or "")
    name_norm = _normalize_for_search(name)
    if not name_norm:
        return False
    tokens = [t.strip() for t in query.strip().split() if t.strip()]
    for token in tokens:
        token_norm = _normalize_for_search(token)
        if not token_norm or token_norm not in name_norm:
            return False
    return True


def filter_products(
    products: List[Dict[str, Any]],
    missing_flags: List[str],
    producer: str,
    exclude_producer: str,
    search_query: str = "",
    filter_column: Optional[str] = None,
    filter_empty: Optional[int] = None,
    filter_values: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    producer = (producer or "").strip().lower()
    exclude_producer = (exclude_producer or "").strip().lower()
    search_query = (search_query or "").strip()

    allowed_columns = set(PRODUCT_KEYS)
    use_value_filter = (
        filter_column
        and filter_column in allowed_columns
        and filter_values
        and len(filter_values) > 0
    )
    use_column_filter = (
        filter_column and filter_column in allowed_columns and filter_empty is not None
    ) and not use_value_filter

    for p in products:
        short_producer = str(producer_short_value(p.get("Nazwa_producenta")) or "").strip()

        if producer and short_producer.lower() != producer:
            continue
        if exclude_producer and short_producer.lower() == exclude_producer:
            continue

        if use_value_filter:
            val = p.get(filter_column)
            str_val = "" if val is None else str(val).strip()
            if str_val not in filter_values:
                continue
        elif use_column_filter:
            empty = is_column_empty(p, filter_column)
            if filter_empty == 1 and not empty:
                continue
            if filter_empty == 0 and empty:
                continue
        else:
            ok = True
            for flag in missing_flags:
                if flag == "missing_producer" and not is_missing(p.get("Nazwa_producenta")):
                    ok = False
                    break
                if flag == "missing_sku" and not is_missing(p.get("SKU")):
                    ok = False
                    break
                if flag == "missing_ean" and not is_missing(p.get("EAN")):
                    ok = False
                    break
                if flag == "missing_weight" and not is_missing_weight(p.get("Waga_brutto")):
                    ok = False
                    break
            if not ok:
                continue

        if search_query and not _product_matches_search(p, search_query):
            continue
        result.append(p)
    return result


def paginate(items: List[Dict[str, Any]], page: int, page_size: int) -> Tuple[List[Dict[str, Any]], int]:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total


def save_products(products: List[Dict[str, Any]], user_id: Optional[str] = None, action: str = "edit") -> None:
    """
    Zapisuje produkty do pliku.
    Jeśli historia jest włączona i podano user_id, tworzy snapshot przed zapisem.
    """
    # Zapisz snapshot przed zmianą (jeśli historia włączona)
    if HISTORY_ENABLED and user_id:
        try:
            current_products = load_products()
            save_snapshot(user_id, current_products, action)
        except Exception:
            pass  # Jeśli snapshot się nie powiedzie, kontynuuj zapis
    
    DATA_FILE.write_text(
        json.dumps(products, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _DATA_CACHE["products"] = products
    _DATA_CACHE["mtime"] = DATA_FILE.stat().st_mtime


def _ensure_views_dir() -> None:
    VIEWS_DIR.mkdir(parents=True, exist_ok=True)


def list_column_views() -> List[Dict[str, Any]]:
    """Zwraca listę zapisanych widoków kolumn (z plików JSON w katalogu column_views)."""
    _ensure_views_dir()
    views: List[Dict[str, Any]] = []
    for path in sorted(VIEWS_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            views.append(
                {
                    "id": path.stem,
                    "label": payload.get("label", path.stem),
                    "profile": payload.get("profile", {}),
                }
            )
        except Exception:
            continue
    return views


def save_column_view(author: str, profile: Dict[str, bool]) -> Dict[str, Any]:
    """
    Zapisuje widok kolumn do pliku JSON.
    Nazwa pliku: imię_DD-MM-RRRR_GG-MM.json
    """
    _ensure_views_dir()
    safe_author = "".join(ch for ch in author.strip() if ch.isalnum() or ch in ("_", "-"))
    if not safe_author:
        safe_author = "user"
    ts = datetime.now().strftime("%d-%m-%Y_%H-%M")
    label = f"{safe_author}_{ts}"
    path = VIEWS_DIR / f"{label}.json"

    payload = {
        "label": label,
        "author": safe_author,
        "created_at": ts,
        "profile": profile,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"id": path.stem, "label": label, "profile": profile}


def load_stats() -> Dict[str, Any]:
    """Wczytuje statystyki z pliku JSON."""
    if not STATS_FILE.exists():
        return {"modified_count": 0}
    try:
        raw = STATS_FILE.read_text(encoding="utf-8")
        return json.loads(raw)
    except Exception:
        return {"modified_count": 0}


def save_stats(stats: Dict[str, Any]) -> None:
    """Zapisuje statystyki do pliku JSON."""
    STATS_FILE.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def increment_modified_count() -> int:
    """Zwiększa licznik zmodyfikowanych rekordów o 1 i zwraca nową wartość."""
    stats = load_stats()
    stats["modified_count"] = stats.get("modified_count", 0) + 1
    save_stats(stats)
    return stats["modified_count"]


@app.route("/")
def index():
    products = load_products()
    stats = load_stats()

    total_count = len(products)

    # wybrane – na razie 0 (brak mechanizmu zaznaczania)
    selected_count = 0

    missing_producer = sum(
        1 for p in products if is_missing(p.get("Nazwa_producenta"))
    )
    missing_sku = sum(1 for p in products if is_missing(p.get("SKU")))
    missing_ean = sum(1 for p in products if is_missing(p.get("EAN")))
    # Niedostępnych: Dostepnosc puste, 0 lub status „niedostępny” / „niedostepny”
    def _is_unavailable(v):
        if v is None:
            return True
        s = str(v).strip()
        if s == "":
            return True
        s_lower = s.lower()
        if s_lower in ("0", "niedostępne", "niedostepne", "niedostępny", "niedostepny"):
            return True
        return False
    unavailable_count = sum(1 for p in products if _is_unavailable(p.get("Dostepnosc")))

    modified_count = stats.get("modified_count", 0)
    version = read_version()

    return render_template(
        "index.html",
        total_count=total_count,
        selected_count=selected_count,
        missing_producer=missing_producer,
        missing_sku=missing_sku,
        missing_ean=missing_ean,
        unavailable_count=unavailable_count,
        modified_count=modified_count,
        version=version,
        use_db=_use_db(),
    )


@app.get("/api/products")
def get_products_paginated():
    products = load_products()

    raw_missing = request.args.get("missing", "")
    missing_flags = [
        item.strip()
        for item in raw_missing.split(",")
        if item.strip() in {"missing_producer", "missing_sku", "missing_ean", "missing_weight"}
    ]

    # kompatybilnie: można też podać flagi osobno
    for key in ("missing_producer", "missing_sku", "missing_ean", "missing_weight"):
        if parse_bool(request.args.get(key, "0")) and key not in missing_flags:
            missing_flags.append(key)

    producer = request.args.get("producer", "")
    exclude_producer = request.args.get("exclude_producer", "")
    search_query = request.args.get("search", "").strip()
    filter_column = request.args.get("column", "").strip() or None
    filter_empty_raw = request.args.get("empty", "")
    raw_values = request.args.get("values", "")
    filter_values = [v.strip() for v in raw_values.split(",") if v.strip()] or None
    filter_empty = None
    if filter_column and filter_empty_raw in ("0", "1"):
        filter_empty = int(filter_empty_raw)
    if filter_column and filter_empty is None and not (filter_values and len(filter_values) > 0):
        filter_column = None
    if filter_column and filter_values is not None and len(filter_values) == 0:
        filter_values = None

    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get("page_size", 200))
    except ValueError:
        page_size = 200
    page_size = min(max(page_size, 50), 2000)

    filtered = filter_products(
        products=products,
        missing_flags=missing_flags,
        producer=producer,
        exclude_producer=exclude_producer,
        search_query=search_query,
        filter_column=filter_column,
        filter_empty=filter_empty,
        filter_values=filter_values,
    )

    sort_by = (request.args.get("sort_by") or "").strip()
    sort_order = (request.args.get("order") or "asc").strip().lower()
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"
    if sort_by and sort_by in PRODUCT_KEYS:
        reverse = sort_order == "desc"
        numeric_keys = DB_NUMERIC_KEYS
        def _sort_key(p):
            v = p.get(sort_by)
            if v is None or (isinstance(v, str) and v.strip() == ""):
                return (0, 0, 0) if not reverse else (0, 1, 0)
            if sort_by in numeric_keys:
                try:
                    n = float(v) if isinstance(v, str) and ("." in v or "e" in str(v).lower()) else int(float(v))
                    return (1, 0, n)
                except (ValueError, TypeError):
                    return (1, 1, (str(v).lower() if v is not None else ""))
            return (1, 0, (str(v).lower() if v is not None else ""))
        filtered = sorted(filtered, key=_sort_key, reverse=reverse)

    page_items, total_filtered = paginate(filtered, page=page, page_size=page_size)

    return jsonify(
        {
            "items": page_items,
            "page": page,
            "page_size": page_size,
            "total_filtered": total_filtered,
            "total_all": len(products),
            "total_pages": (total_filtered + page_size - 1) // page_size if page_size else 1,
        }
    )


@app.get("/api/column-values")
def get_column_values():
    """Zwraca unikalne (niepuste) wartości z danej kolumny – do filtrów w kryteriach."""
    try:
        column = (request.args.get("column") or "").strip()
        if not column or column not in PRODUCT_KEYS:
            return jsonify({"column": column or "", "values": []})
        products = load_products()
        if not isinstance(products, list):
            return jsonify({"column": column, "values": []})
        seen = set()
        out = []
        for p in products:
            if not isinstance(p, dict):
                continue
            v = p.get(column)
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            s = str(v).strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
        out.sort(key=lambda x: (x.lower(), x))
        return jsonify({"column": column, "values": out})
    except Exception:
        return jsonify({"column": request.args.get("column", ""), "values": []})


@app.get("/api/duplicates")
def get_duplicates():
    """
    Raport duplikatów: by=ean lub by=sku.
    Zwraca wartości występujące więcej niż raz (do weryfikacji ręcznej).
    """
    by = (request.args.get("by") or "ean").strip().lower()
    if by not in ("ean", "sku"):
        by = "ean"
    field = "EAN" if by == "ean" else "SKU"
    products = load_products()
    from collections import defaultdict
    counts = defaultdict(list)
    for p in products:
        val = p.get(field)
        if val is not None and str(val).strip():
            counts[str(val).strip()].append(p.get("id") or p.get("ID_produktu"))
    duplicates = [{"value": v, "count": len(ids), "ids": ids[:10]} for v, ids in counts.items() if len(ids) > 1]
    return jsonify({"by": by, "field": field, "duplicates": duplicates, "total_duplicate_values": len(duplicates)})


@app.get("/api/producers")
def get_producers():
    products = load_products()
    seen = set()
    out = []
    for p in products:
        name = producer_short_value(p.get("Nazwa_producenta"))
        if not isinstance(name, str):
            continue
        name = name.strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    out.sort(key=lambda x: x.lower())
    return jsonify({"producers": out})


@app.patch("/api/products/<int:product_id>")
def update_product_field(product_id: int):
    data = request.get_json(silent=True) or {}
    field = str(data.get("field", "")).strip()
    value = data.get("value")
    user_id = data.get("user_id", "").strip() or None

    if not field:
        return jsonify({"error": "field_required"}), 400
    if field == "ID_produktu":
        return jsonify({"error": "field_not_editable"}), 400

    if _use_db():
        with get_connection() as conn:
            ensure_extra_tables(conn)
            if not db_update_product(conn, product_id, field, value):
                return jsonify({"error": "product_not_found"}), 404
            try:
                p = get_product(conn, product_id)
                if p and user_id:
                    insert_change_log(conn, user_id, int(p.get("ID_produktu") or 0), field, value)
            except Exception:
                pass  # nie blokuj zapisu gdy dziennik się nie uda
        modified_count = increment_modified_count()
        cast_value = value.strip() if isinstance(value, str) else value
        return jsonify({
            "ok": True,
            "product_id": product_id,
            "field": field,
            "value": cast_value,
            "modified_count": modified_count,
        })

    products = load_products()
    target = None
    for p in products:
        if int(p.get("ID_produktu", -1)) == product_id:
            target = p
            break
    if target is None:
        return jsonify({"error": "product_not_found"}), 404

    if isinstance(value, str):
        cast_value: Any = value.strip()
    else:
        cast_value = value

    target[field] = cast_value
    save_products(products, user_id=user_id, action="edit")
    modified_count = increment_modified_count()

    return jsonify(
        {
            "ok": True,
            "product_id": product_id,
            "field": field,
            "value": cast_value,
            "modified_count": modified_count,
        }
    )


@app.post("/api/products/batch-delete")
def batch_delete_products():
    """
    Usuwa wiele produktów na raz. Gdy DB: ids to PK. Gdy plik: ids to ID_produktu.
    Oczekuje JSON-a: {"ids": [123, 456, ...], "user_id": "nazwa"}
    """
    data = request.get_json(silent=True) or {}
    raw_ids = data.get("ids") or []
    user_id = data.get("user_id", "").strip() or None

    try:
        ids = [int(x) for x in raw_ids]
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_ids"}), 400

    if not ids:
        return jsonify({"deleted": 0, "remaining": len(load_products())})

    if _use_db():
        with get_connection() as conn:
            deleted = delete_products_by_ids(conn, ids)
        remaining = len(load_products())
        return jsonify({"deleted": deleted, "remaining": remaining})

    products = load_products()
    id_set = {int(x) for x in ids}
    kept: List[Dict[str, Any]] = []
    deleted = 0
    for p in products:
        pid = int(p.get("ID_produktu", -1))
        if pid in id_set:
            deleted += 1
        else:
            kept.append(p)

    if deleted == 0:
        return jsonify({"deleted": 0, "remaining": len(products)})

    save_products(kept, user_id=user_id, action="delete")
    return jsonify({"deleted": deleted, "remaining": len(kept)})


@app.post("/api/products/batch-update")
def batch_update_products():
    """
    Aktualizuje wiele produktów na raz. Gdy DB: ids to PK. Gdy plik: ids to ID_produktu.
    Oczekuje JSON-a: {"ids": [123, 456, ...], "field": "...", "value": "...", "user_id": "nazwa"}
    """
    data = request.get_json(silent=True) or {}
    raw_ids = data.get("ids") or []
    field = str(data.get("field", "")).strip()
    value = data.get("value")
    user_id = data.get("user_id", "").strip() or None

    if not field:
        return jsonify({"error": "field_required"}), 400
    if field == "ID_produktu":
        return jsonify({"error": "field_not_editable"}), 400

    try:
        ids = [int(x) for x in raw_ids]
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_ids"}), 400

    if not ids:
        return jsonify({"updated": 0})

    if _use_db():
        with get_connection() as conn:
            ensure_extra_tables(conn)
            updated = db_batch_update_products(conn, ids, field, value)
            try:
                if updated and user_id:
                    id_produktu_list = get_products_id_produktu(conn, ids)
                    for i in range(updated):
                        insert_change_log(conn, user_id, id_produktu_list[i], field, value)
            except Exception:
                pass  # nie blokuj zapisu gdy dziennik się nie uda
        return jsonify({"updated": updated, "updated_ids": ids[:updated]})

    id_set = set(ids)
    products = load_products()
    updated = 0
    updated_ids = []
    cast_value: Any = value.strip() if isinstance(value, str) else value

    for p in products:
        pid = int(p.get("ID_produktu", -1))
        if pid in id_set:
            p[field] = cast_value
            updated += 1
            updated_ids.append(pid)

    if updated > 0:
        save_products(products, user_id=user_id, action="batch_edit")

    return jsonify({"updated": updated, "updated_ids": updated_ids})


@app.get("/column-views")
def get_column_views():
    """Zwraca listę zapisanych widoków kolumn."""
    views = list_column_views()
    return jsonify({"views": views})


@app.post("/column-views")
def create_column_view():
    """
    Zapisuje nowy widok kolumn.
    Oczekuje JSON-a: {"author": "Imię", "profile": {kolumna: bool, ...}}
    """
    data = request.get_json(silent=True) or {}
    author = str(data.get("author", "")).strip()
    profile = data.get("profile")

    if not author:
        return jsonify({"error": "author_required"}), 400
    if not isinstance(profile, dict):
        return jsonify({"error": "profile_required"}), 400

    view = save_column_view(author, profile)
    return jsonify(view), 201


@app.get("/api/stats")
def get_stats():
    """Zwraca statystyki (m.in. licznik zmodyfikowanych rekordów)."""
    stats = load_stats()
    return jsonify(stats)


@app.post("/api/stats/reset-modified")
def reset_modified_count():
    """Resetuje licznik zmodyfikowanych rekordów do 0."""
    stats = load_stats()
    stats["modified_count"] = 0
    save_stats(stats)
    return jsonify({"modified_count": 0})


def read_version() -> str:
    """Czyta aktualną wersję z pliku VERSION.txt"""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "1.0.0"


@app.get("/api/version")
def get_version():
    """Zwraca aktualną wersję aplikacji."""
    return jsonify({"version": read_version()})


@app.get("/api/history")
def get_history():
    """Zwraca listę historii zmian dla użytkownika."""
    if not HISTORY_ENABLED:
        return jsonify({"history": [], "enabled": False})
    
    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"history": [], "enabled": True})
    
    history = get_history_list(user_id)
    return jsonify({"history": history, "enabled": True})


@app.post("/api/history/undo")
def undo_change():
    """
    Cofa ostatnią zmianę użytkownika.
    Oczekuje JSON-a: {"user_id": "nazwa"}
    """
    if not HISTORY_ENABLED:
        return jsonify({"error": "history_disabled"}), 400
    
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    
    if not user_id:
        return jsonify({"error": "user_id_required"}), 400
    
    history = get_history_list(user_id)
    if not history:
        return jsonify({"error": "no_history"}), 404
    
    # Załaduj najnowszy snapshot (przed ostatnią zmianą)
    snapshot_id = history[0]["id"]
    products = load_snapshot(user_id, snapshot_id)
    
    if products is None:
        return jsonify({"error": "snapshot_not_found"}), 404
    
    # Zapisz cofnięty stan BEZ tworzenia nowego snapshotu (używamy bezpośredniego zapisu)
    # To zapobiega tworzeniu snapshotu przy cofaniu
    DATA_FILE.write_text(
        json.dumps(products, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _DATA_CACHE["products"] = products
    _DATA_CACHE["mtime"] = DATA_FILE.stat().st_mtime
    
    # Usuń najnowszy snapshot z historii (ten który właśnie cofnęliśmy)
    try:
        from history_manager import get_user_history_dir
        user_dir = get_user_history_dir(user_id)
        snapshot_file = user_dir / f"{snapshot_id}.json.gz"
        if snapshot_file.exists():
            snapshot_file.unlink()
    except Exception:
        pass
    
    return jsonify({
        "success": True,
        "message": "Zmiany cofnięte",
        "snapshot_id": snapshot_id,
    })


@app.post("/api/history/clear")
def clear_user_history():
    """Czyści historię użytkownika."""
    if not HISTORY_ENABLED:
        return jsonify({"error": "history_disabled"}), 400
    
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    
    if not user_id:
        return jsonify({"error": "user_id_required"}), 400
    
    clear_history(user_id)
    return jsonify({"success": True, "message": "Historia wyczyszczona"})


@app.post("/api/database/upload")
def upload_database():
    """
    Upload: JSON lub XML. Gdy DB – import do bazy (source=json/xml). Gdy plik – tylko JSON, nadpisuje plik.
    Multipart/form-data z plikiem 'file'.
    """
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "empty_filename"}), 400

    fn = (file.filename or "").lower()
    is_xml = fn.endswith(".xml")
    is_json = fn.endswith(".json")

    if not (is_json or is_xml):
        return jsonify({"error": "invalid_file_type", "hint": "Dozwolone: .json, .xml"}), 400

    if _use_db() and (is_json or is_xml):
        try:
            content = file.read()
            if is_json:
                data = load_from_json_bytes(content)
                source = "json"
            else:
                data = load_from_xml_suuhouse(content)
                source = "xml"
            existing = load_products()
            if existing:
                merged = _merge_products(existing, data, new_is_master=True)
                data = merged
                msg = f"Scalono z bieżącą bazą: {len(merged)} produktów (plik {source} ma pierwszeństwo przy konfliktach)"
            else:
                msg = f"Zaimportowano {len(data)} produktów ({source}) do bazy"
            with get_connection() as conn:
                clear_products(conn)
                insert_products(conn, data, source=source)
            return jsonify({
                "success": True,
                "message": msg,
                "count": len(data),
                "source": source,
            })
        except ValueError as e:
            return jsonify({"error": "invalid_format", "detail": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if not is_json:
        return jsonify({"error": "invalid_file_type", "hint": "Bez bazy dozwolony tylko plik .json"}), 400

    try:
        content = file.read().decode("utf-8")
        data = json.loads(content)
        if not isinstance(data, list):
            return jsonify({"error": "invalid_json_format"}), 400

        backup_file = BASE_DIR / f"backup_before_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        if DATA_FILE.exists():
            shutil.copy2(DATA_FILE, backup_file)

        DATA_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _DATA_CACHE["products"] = []
        _DATA_CACHE["mtime"] = None

        return jsonify({
            "success": True,
            "message": f"Załadowano {len(data)} produktów",
            "count": len(data),
        })
    except json.JSONDecodeError:
        return jsonify({"error": "invalid_json"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/database/clear")
def clear_database():
    """
    Wyzerowuje dane. Gdy DB – czyści tabelę products. Gdy plik – zapisuje pustą listę.
    Wymaga confirm: true.
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    confirm = data.get("confirm", False)

    if not confirm:
        return jsonify({"error": "confirmation_required"}), 400

    try:
        if _use_db():
            with get_connection() as conn:
                n = clear_products(conn)
            return jsonify({"success": True, "message": f"Baza wyzerowana ({n} usuniętych)", "deleted": n})

        backup_file = BASE_DIR / f"backup_before_clear_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        if DATA_FILE.exists():
            shutil.copy2(DATA_FILE, backup_file)
        DATA_FILE.write_text("[]", encoding="utf-8")
        _DATA_CACHE["products"] = []
        _DATA_CACHE["mtime"] = None
        return jsonify({"success": True, "message": "Baza danych wyzerowana"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/database/download")
def download_database():
    """
    Zwraca aktualną bazę jako JSON do pobrania (ta sama struktura kolumn co wejściowy JSON).
    Gdy DB: eksport z bazy (bez pól id/source). Gdy plik: zwraca plik.
    """
    user_id = request.args.get("user_id", "").strip()

    try:
        products = load_products()

        if user_id and HISTORY_ENABLED:
            try:
                from history_manager import get_user_history_dir
                user_dir = get_user_history_dir(user_id)
                work_dir = user_dir / "work"
                work_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                work_file = work_dir / f"database_{timestamp}.json"
                export_list = [{k: p.get(k) for k in PRODUCT_KEYS} for p in products] if _use_db() else products
                work_file.write_text(
                    json.dumps(export_list, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass

        if _use_db():
            export_list = [{k: p.get(k) for k in PRODUCT_KEYS} for p in products]
            buf = BytesIO(json.dumps(export_list, ensure_ascii=False, indent=2).encode("utf-8"))
            return send_file(
                buf,
                mimetype="application/json",
                as_attachment=True,
                download_name=f"AsortymentyMasterData_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            )

        return send_file(
            str(DATA_FILE),
            mimetype="application/json",
            as_attachment=True,
            download_name=f"AsortymentyMasterData_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/backup")
def create_backup_endpoint():
    """
    Tworzy backup na żądanie.
    Oczekuje JSON-a: {"type": "backup" | "stable"}
    """
    data = request.get_json(silent=True) or {}
    backup_type = data.get("type", "backup")
    
    try:
        import sys
        python_exe = sys.executable  # Użyj tego samego interpretera Python
        
        if backup_type == "stable":
            # Wersja stabilna - zwiększa minor version
            result = subprocess.run(
                [python_exe, str(BASE_DIR / "backup.py"), "stabilna"],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"  # Zastąp niepoprawne znaki
            )
            if result.returncode == 0:
                # Utwórz tag Git
                version = read_version()
                tag_name = f"v{version}"
                git_result = subprocess.run(
                    ["git", "tag", tag_name, "-m", f"Stable version {version}"],
                    cwd=str(BASE_DIR),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
                
                # Automatyczny push do GitHub (jeśli remote jest skonfigurowany)
                try:
                    # Sprawdź czy istnieje remote origin
                    check_remote = subprocess.run(
                        ["git", "remote", "get-url", "origin"],
                        cwd=str(BASE_DIR),
                        capture_output=True,
                        text=True
                    )
                    
                    if check_remote.returncode == 0:
                        # Push commitów i tagów do GitHub
                        push_result = subprocess.run(
                            ["git", "push", "origin", "main"],
                            cwd=str(BASE_DIR),
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            timeout=30
                        )
                        push_tags_result = subprocess.run(
                            ["git", "push", "origin", "--tags"],
                            cwd=str(BASE_DIR),
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            timeout=30
                        )
                except Exception:
                    # Jeśli push się nie powiedzie, nie blokuj - backup lokalny jest ważniejszy
                    pass
                
                return jsonify({
                    "success": True,
                    "message": f"Utworzono wersję stabilną {version} i wysłano na GitHub",
                    "version": version,
                    "output": result.stdout.strip()
                })
            else:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Błąd podczas tworzenia backupu"
                return jsonify({
                    "success": False,
                    "error": error_msg
                }), 500
        else:
            # Zwykły backup - zwiększa patch version
            result = subprocess.run(
                [python_exe, str(BASE_DIR / "backup.py"), "kopie"],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"  # Zastąp niepoprawne znaki
            )
            if result.returncode == 0:
                version = read_version()
                return jsonify({
                    "success": True,
                    "message": f"Utworzono backup wersji {version}",
                    "version": version,
                    "output": result.stdout.strip()
                })
            else:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Błąd podczas tworzenia backupu"
                return jsonify({
                    "success": False,
                    "error": error_msg
                }), 500
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return jsonify({
            "success": False,
            "error": f"{str(e)}\n{error_details}"
        }), 500


@app.post("/api/work/save")
def save_work():
    """
    Zapisuje bieżącą bazę. Gdy Postgres: do tabeli user_saved_bases (max 3 na usera).
    Gdy plik: do katalogu work użytkownika. Oczekuje JSON: {"user_id": "nazwa"}
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    
    if not user_id:
        return jsonify({"error": "user_id_required"}), 400
    
    try:
        products = load_products()
        
        if _use_db():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS user_saved_bases (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            data JSONB NOT NULL
                        )
                    """)
                base_id = save_user_base(conn, user_id, products)
            return jsonify({
                "success": True,
                "message": f"Baza zapisana (zapis #{base_id})",
                "filename": f"baza_{base_id}.json",
            })
        
        if not HISTORY_ENABLED:
            return jsonify({"error": "history_not_enabled"}), 500
        
        from history_manager import get_user_history_dir
        user_dir = get_user_history_dir(user_id)
        work_dir = user_dir / "work"
        work_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        work_file = work_dir / f"{user_id}_{timestamp}.json"
        
        work_file.write_text(
            json.dumps(products, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        
        return jsonify({
            "success": True,
            "message": f"Praca zapisana: {work_file.name}",
            "filename": work_file.name,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/work/list")
def list_work_files():
    """
    Lista zapisanych baz. Gdy Postgres: 3 ostatnie z user_saved_bases. Gdy plik: z katalogu work.
    Query param: user_id
    """
    user_id = request.args.get("user_id", "").strip()
    
    if not user_id:
        return jsonify({"error": "user_id_required"}), 400
    
    try:
        if _use_db():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS user_saved_bases (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            data JSONB NOT NULL
                        )
                    """)
                files = list_user_bases(conn, user_id)
            return jsonify({"files": files})
        
        if not HISTORY_ENABLED:
            return jsonify({"files": []})
        
        from history_manager import get_user_history_dir
        user_dir = get_user_history_dir(user_id)
        work_dir = user_dir / "work"
        
        if not work_dir.exists():
            return jsonify({"files": []})
        
        files = []
        for file_path in sorted(work_dir.glob(f"{user_id}_*.json"), reverse=True):
            files.append({
                "filename": file_path.name,
                "timestamp": file_path.stem.replace(f"{user_id}_", ""),
                "size": file_path.stat().st_size,
            })
        
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/work/load")
def load_work():
    """
    Wczytuje zapisaną bazę. Gdy Postgres: z user_saved_bases po id (filename=baza_<id>.json).
    Gdy plik: z katalogu work. JSON: {"user_id", "filename"}
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    filename = data.get("filename", "").strip()
    
    if not user_id or not filename:
        return jsonify({"error": "user_id_and_filename_required"}), 400
    
    try:
        if _use_db():
            # filename z list to "baza_123.json" -> base_id 123
            base_id = None
            if filename.startswith("baza_") and filename.endswith(".json"):
                try:
                    base_id = int(filename[5:-5])
                except ValueError:
                    pass
            if base_id is None:
                return jsonify({"error": "invalid_filename_for_db"}), 400
            with get_connection() as conn:
                products = get_user_base(conn, base_id, user_id)
            if products is None:
                return jsonify({"error": "file_not_found"}), 404
            if not isinstance(products, list):
                return jsonify({"error": "invalid_json_format"}), 400
            with get_connection() as conn:
                clear_products(conn)
                insert_products(conn, products, source="json")
            _DATA_CACHE["products"] = []
            _DATA_CACHE["mtime"] = None
            return jsonify({
                "success": True,
                "message": f"Wczytano {len(products)} produktów",
                "count": len(products),
            })
        
        if not HISTORY_ENABLED:
            return jsonify({"error": "history_not_enabled"}), 500
        
        from history_manager import get_user_history_dir
        user_dir = get_user_history_dir(user_id)
        work_dir = user_dir / "work"
        work_file = work_dir / filename
        
        if not work_file.exists():
            return jsonify({"error": "file_not_found"}), 404
        
        content = work_file.read_text(encoding="utf-8")
        products = json.loads(content)
        
        if not isinstance(products, list):
            return jsonify({"error": "invalid_json_format"}), 400
        
        backup_file = BASE_DIR / f"backup_before_load_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        if DATA_FILE.exists():
            shutil.copy2(DATA_FILE, backup_file)
        DATA_FILE.write_text(
            json.dumps(products, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _DATA_CACHE["products"] = []
        _DATA_CACHE["mtime"] = None
        
        return jsonify({
            "success": True,
            "message": f"Wczytano {len(products)} produktów z pliku {filename}",
            "count": len(products),
        })
    except json.JSONDecodeError:
        return jsonify({"error": "invalid_json"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/backup/create")
def api_backup_create():
    """Tworzy kopię systemową (max 3, rotacja). Tylko Postgres."""
    if not _use_db():
        return jsonify({"error": "database_required"}), 400
    try:
        with get_connection() as conn:
            ensure_extra_tables(conn)
            backup_id = create_system_backup(conn)
        return jsonify({"success": True, "message": f"Kopia utworzona (#{backup_id})", "backup_id": backup_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/restore-from-backup")
def api_restore_from_backup():
    """Przywraca bazę z najnowszej kopii systemowej. Tylko Postgres."""
    if not _use_db():
        return jsonify({"error": "database_required"}), 400
    try:
        with get_connection() as conn:
            ensure_extra_tables(conn)
            if not restore_from_latest_backup(conn):
                return jsonify({"error": "no_backup"}), 404
        _DATA_CACHE["products"] = []
        _DATA_CACHE["mtime"] = None
        return jsonify({"success": True, "message": "Baza przywrócona z kopii"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/changes-since")
def api_changes_since():
    """Zmiany po id (polling – odświeżanie na żywo w innych oknach). Query: after_id."""
    if not _use_db():
        return jsonify({"changes": []})
    try:
        after_id = request.args.get("after_id", "0")
        try:
            after_id = int(after_id)
        except (TypeError, ValueError):
            after_id = 0
        with get_connection() as conn:
            ensure_extra_tables(conn)
            changes = get_changes_since(conn, after_id=after_id)
        return jsonify({"changes": changes})
    except Exception as e:
        return jsonify({"error": str(e), "changes": []}), 500


@app.get("/api/change-log")
def api_change_log():
    """Dziennik zmian pogrupowany po datach (dziś, wczoraj, DD-MM). Tylko Postgres."""
    if not _use_db():
        return jsonify({"groups": []})
    try:
        with get_connection() as conn:
            ensure_extra_tables(conn)
            groups = get_change_log_grouped(conn)
        return jsonify({"groups": groups})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Uruchomienie lokalne: py app.py
    app.run(debug=True)

