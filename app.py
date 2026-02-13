import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from flask import Flask, render_template, request, jsonify
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
    """Wczytuje listę produktów z pliku JSON."""
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
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    producer = (producer or "").strip().lower()
    exclude_producer = (exclude_producer or "").strip().lower()
    search_query = (search_query or "").strip()

    for p in products:
        short_producer = str(producer_short_value(p.get("Nazwa_producenta")) or "").strip()

        if producer and short_producer.lower() != producer:
            continue
        if exclude_producer and short_producer.lower() == exclude_producer:
            continue

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

    modified_count = stats.get("modified_count", 0)
    version = read_version()

    return render_template(
        "index.html",
        total_count=total_count,
        selected_count=selected_count,
        missing_producer=missing_producer,
        missing_sku=missing_sku,
        missing_ean=missing_ean,
        modified_count=modified_count,
        version=version,
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

    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get("page_size", 200))
    except ValueError:
        page_size = 200
    page_size = min(max(page_size, 50), 500)

    filtered = filter_products(
        products=products,
        missing_flags=missing_flags,
        producer=producer,
        exclude_producer=exclude_producer,
        search_query=search_query,
    )
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

    products = load_products()
    target = None
    for p in products:
        if int(p.get("ID_produktu", -1)) == product_id:
            target = p
            break
    if target is None:
        return jsonify({"error": "product_not_found"}), 404

    # Puste inputy zapisujemy jako pusty string.
    if isinstance(value, str):
        cast_value: Any = value.strip()
    else:
        cast_value = value

    target[field] = cast_value
    save_products(products, user_id=user_id, action="edit")
    
    # Zwiększ licznik zmodyfikowanych rekordów
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
    Usuwa wiele produktów na raz na podstawie listy ID_produktu.
    Oczekuje JSON-a: {"ids": [123, 456, ...], "user_id": "nazwa"}
    """
    data = request.get_json(silent=True) or {}
    raw_ids = data.get("ids") or []
    user_id = data.get("user_id", "").strip() or None
    
    try:
        ids = {int(x) for x in raw_ids}
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_ids"}), 400

    if not ids:
        return jsonify({"deleted": 0, "remaining": len(load_products())})

    products = load_products()
    kept: List[Dict[str, Any]] = []
    deleted = 0
    for p in products:
        pid = int(p.get("ID_produktu", -1))
        if pid in ids:
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
    Aktualizuje wiele produktów na raz - ustawia to samo pole na tę samą wartość.
    Oczekuje JSON-a: {"ids": [123, 456, ...], "field": "Nazwa_producenta", "value": "SALAG", "user_id": "nazwa"}
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
        ids = {int(x) for x in raw_ids}
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_ids"}), 400

    if not ids:
        return jsonify({"updated": 0})

    products = load_products()
    updated = 0
    updated_ids = []

    # Puste inputy zapisujemy jako pusty string.
    if isinstance(value, str):
        cast_value: Any = value.strip()
    else:
        cast_value = value

    for p in products:
        pid = int(p.get("ID_produktu", -1))
        if pid in ids:
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
    Uploaduje nowy plik JSON jako bazę danych.
    Oczekuje multipart/form-data z plikiem 'file'.
    """
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "empty_filename"}), 400
    
    if not file.filename.endswith(".json"):
        return jsonify({"error": "invalid_file_type"}), 400
    
    try:
        # Wczytaj i zweryfikuj JSON
        content = file.read().decode("utf-8")
        data = json.loads(content)
        
        # Sprawdź czy to lista produktów
        if not isinstance(data, list):
            return jsonify({"error": "invalid_json_format"}), 400
        
        # Zapisz jako backup przed zmianą
        backup_file = BASE_DIR / f"backup_before_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        if DATA_FILE.exists():
            shutil.copy2(DATA_FILE, backup_file)
        
        # Zapisz nowy plik
        DATA_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        
        # Wyczyść cache
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
    Wyzerowuje bazę danych (zapisuje pustą listę).
    Wymaga potwierdzenia przez user_id.
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    confirm = data.get("confirm", False)
    
    if not confirm:
        return jsonify({"error": "confirmation_required"}), 400
    
    try:
        # Zapisz jako backup przed wyzerowaniem
        backup_file = BASE_DIR / f"backup_before_clear_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        if DATA_FILE.exists():
            shutil.copy2(DATA_FILE, backup_file)
        
        # Wyzeruj bazę
        DATA_FILE.write_text("[]", encoding="utf-8")
        
        # Wyczyść cache
        _DATA_CACHE["products"] = []
        _DATA_CACHE["mtime"] = None
        
        return jsonify({
            "success": True,
            "message": "Baza danych wyzerowana",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/database/download")
def download_database():
    """
    Zwraca aktualną bazę danych jako JSON do pobrania.
    Query param: user_id - identyfikator użytkownika (do zapisu w katalogu work)
    """
    from flask import send_file
    
    user_id = request.args.get("user_id", "").strip()
    
    try:
        products = load_products()
        
        # Jeśli podano user_id, zapisz kopię w katalogu work użytkownika
        if user_id and HISTORY_ENABLED:
            try:
                from history_manager import get_user_history_dir
                user_dir = get_user_history_dir(user_id)
                work_dir = user_dir / "work"
                work_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                work_file = work_dir / f"database_{timestamp}.json"
                
                work_file.write_text(
                    json.dumps(products, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass  # Jeśli zapis w work się nie powiedzie, kontynuuj pobieranie
        
        # Zwróć plik do pobrania
        return send_file(
            str(DATA_FILE),
            mimetype="application/json",
            as_attachment=True,
            download_name=f"AsortymentyMasterData_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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


if __name__ == "__main__":
    # Uruchomienie lokalne: py app.py
    app.run(debug=True)

