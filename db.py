# -*- coding: utf-8 -*-
"""
PostgreSQL – produkty master data.
Tabela products: id (PK), source (json/xml), kolumny jak w pliku JSON.
"""
import os
from contextlib import contextmanager
from typing import Dict, Any, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

# Kolumny z pliku JSON (kolejność i nazwy)
# Tryb = workflow: nowe | w trakcie | gotowe (dodatkowa kolumna)
PRODUCT_KEYS = [
    "ID_produktu", "Tryb", "Status_produktu", "SKU", "Nazwa", "URL_Miniatura",
    "Rodzaj_produktu", "Grupa_produktu", "EAN", "JM_sprzedazy", "Waga_brutto",
    "JM_wagi", "Dlugosc", "Szerokosc", "Wysokosc", "JM_wymiaru",
    "Objetosc_produktu", "JM_objetosci", "Rodzaj_opakowania", "ID_producenta",
    "Nazwa_producenta", "Cena_zakupu_netto", "Cena_zakupu_brutto", "Waluta_zakupu",
    "Nazwa_Cennika", "Cena_sprzedazy_netto", "Cena_sprzedazy_brutto", "Waluta_sprzedazy",
    "Stan_magazynowy", "Rezerwacja", "Dostepnosc",
]

# Kolumny numeryczne (w DB jako NUMERIC, reszta TEXT)
NUMERIC_KEYS = {
    "ID_produktu", "ID_producenta", "Waga_brutto", "Dlugosc", "Szerokosc", "Wysokosc",
    "Objetosc_produktu", "Cena_zakupu_netto", "Cena_zakupu_brutto",
    "Cena_sprzedazy_netto", "Cena_sprzedazy_brutto", "Stan_magazynowy", "Rezerwacja",
}

# Dostepnosc w JSON to liczba, w XML tekst – trzymamy jako TEXT
TEXT_KEYS = set(PRODUCT_KEYS) - NUMERIC_KEYS | {"Dostepnosc"}


def get_database_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL")


@contextmanager
def get_connection():
    url = get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL nie jest ustawiony")
    conn = psycopg2.connect(url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _column_defs() -> str:
    parts = ["id SERIAL PRIMARY KEY", "source VARCHAR(20) NOT NULL DEFAULT 'json'"]
    for k in PRODUCT_KEYS:
        if k in NUMERIC_KEYS:
            parts.append(f'"{k}" NUMERIC')
        else:
            parts.append(f'"{k}" TEXT')
    return ", ".join(parts)


def init_db() -> None:
    """Tworzy tabelę products jeśli nie istnieje."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS products (
                    {_column_defs()}
                )
                """
            )
            try:
                cur.execute("ALTER TABLE products RENAME COLUMN \"Status\" TO \"Tryb\"")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS \"Tryb\" TEXT")
            except Exception:
                pass
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_saved_bases (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    data JSONB NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS base_backups (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    data JSONB NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS change_log (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    user_id TEXT NOT NULL,
                    id_produktu INTEGER NOT NULL,
                    field_name TEXT NOT NULL,
                    new_value TEXT
                )
            """)


def ensure_extra_tables(conn) -> None:
    """Tworzy tabele base_backups i change_log jeśli nie istnieją (np. po wdrożeniu bez restartu)."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS base_backups (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                data JSONB NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS change_log (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                user_id TEXT NOT NULL,
                id_produktu INTEGER NOT NULL,
                field_name TEXT NOT NULL,
                new_value TEXT
            )
        """)


def save_user_base(conn, user_id: str, products: List[Dict[str, Any]]) -> int:
    """Zapisuje bieżącą bazę użytkownika. Maks. 3 zapisy na user_id (najstarsze usuwane). Zwraca id zapisu."""
    import json
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_saved_bases (user_id, data) VALUES (%s, %s::jsonb) RETURNING id",
            (user_id, json.dumps(products, ensure_ascii=False)),
        )
        row = cur.fetchone()
        base_id = row[0]
        cur.execute("""
            DELETE FROM user_saved_bases
            WHERE user_id = %s AND id NOT IN (
                SELECT id FROM user_saved_bases WHERE user_id = %s ORDER BY created_at DESC LIMIT 3
            )
        """, (user_id, user_id))
        return base_id


def list_user_bases(conn, user_id: str) -> List[Dict[str, Any]]:
    """Lista 3 ostatnich zapisów bazy dla user_id. Zwraca listę {id, filename, created_at, size}.
    Czas w timezone Europe/Warsaw (czas lokalny PL)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id,
                   to_char(created_at AT TIME ZONE 'Europe/Warsaw', 'YYYY-MM-DD HH24:MI') AS ts,
                   jsonb_array_length(data) AS cnt, pg_column_size(data) AS bytes
            FROM user_saved_bases
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 3
        """, (user_id,))
        rows = cur.fetchall()
    out = []
    for r in rows:
        ts = r.get("ts") or ""
        out.append({
            "id": r["id"],
            "filename": f"baza_{r['id']}.json",
            "timestamp": ts,
            "size": r.get("bytes") or (r.get("cnt") or 0) * 200,
        })
    return out


def get_user_base(conn, base_id: int, user_id: str) -> Optional[List[Dict[str, Any]]]:
    """Pobiera zapisaną bazę po id (tylko dla danego user_id)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT data FROM user_saved_bases WHERE id = %s AND user_id = %s",
            (base_id, user_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    data = row["data"]
    if isinstance(data, str):
        import json
        data = json.loads(data)
    return data


# --- Kopie systemowe (3 sloty, rotacja) ---
def create_system_backup(conn) -> int:
    """Zapisuje bieżącą bazę do base_backups. Zostaje max 3 kopie (najstarsza znika). Zwraca id backupu."""
    import json
    products = get_all_products(conn)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO base_backups (data) VALUES (%s::jsonb) RETURNING id",
            (json.dumps(products, ensure_ascii=False),),
        )
        row = cur.fetchone()
        backup_id = row[0]
        cur.execute("""
            DELETE FROM base_backups WHERE id NOT IN (
                SELECT id FROM base_backups ORDER BY created_at DESC LIMIT 3
            )
        """)
    return backup_id


def get_latest_backup_data(conn) -> Optional[List[Dict[str, Any]]]:
    """Pobiera dane z najnowszej kopii (lista produktów)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT data FROM base_backups ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
    if not row:
        return None
    data = row["data"]
    if isinstance(data, str):
        import json
        data = json.loads(data)
    return data


def restore_from_latest_backup(conn) -> bool:
    """Nadpisuje tabelę products danymi z najnowszej kopii. Zwraca True jeśli była kopia."""
    data = get_latest_backup_data(conn)
    if not data:
        return False
    clear_products(conn)
    insert_products(conn, data, "json")
    return True


# --- Dziennik zmian ---
def get_product(conn, product_id: int) -> Optional[Dict[str, Any]]:
    """Pobiera jeden produkt po id (PK)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, source, " + ", ".join(f'"{k}"' for k in PRODUCT_KEYS) + " FROM products WHERE id = %s", (product_id,))
        row = cur.fetchone()
    if not row:
        return None
    return _row_to_product(dict(row))


def get_products_id_produktu(conn, ids: List[int]) -> List[int]:
    """Dla listy id (PK) zwraca listę ID_produktu w tej samej kolejności."""
    if not ids:
        return []
    with conn.cursor() as cur:
        cur.execute('SELECT id, "ID_produktu" FROM products WHERE id = ANY(%s)', (ids,))
        rows = cur.fetchall()
    id_to_prod = {r[0]: int(r[1]) if r[1] is not None else 0 for r in rows}
    return [id_to_prod.get(i, 0) for i in ids]


def insert_change_log(conn, user_id: str, id_produktu: int, field_name: str, new_value: Any) -> None:
    """Dodaje wpis do dziennika zmian."""
    val_str = str(new_value).strip() if new_value is not None else ""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO change_log (user_id, id_produktu, field_name, new_value) VALUES (%s, %s, %s, %s)",
            (user_id or "?", id_produktu, field_name, val_str),
        )


def get_changes_since(conn, after_id: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """Zwraca wpisy change_log o id > after_id (do odświeżania na żywo w innych oknach)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, user_id, id_produktu, field_name, new_value,
                   to_char(created_at AT TIME ZONE 'Europe/Warsaw', 'YYYY-MM-DD"T"HH24:MI:SS') AS created_at
            FROM change_log
            WHERE id > %s
            ORDER BY id
            LIMIT %s
        """, (after_id, limit))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_change_log_grouped(conn, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Zwraca wpisy dziennika pogrupowane po dacie.
    Każda grupa: { "date_label": "dziś"|"wczoraj"|"DD-MM", "entries": [ "Marzena, rekord 123, pole X, wartość: Y. DD-MM HH:MM", ... ] }
    Czas w Europe/Warsaw. limit = max wpisów.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT user_id, id_produktu, field_name, new_value,
                   to_char(created_at AT TIME ZONE 'Europe/Warsaw', 'DD-MM') AS d,
                   to_char(created_at AT TIME ZONE 'Europe/Warsaw', 'HH24:MI') AS t,
                   (created_at AT TIME ZONE 'Europe/Warsaw')::date AS dt
            FROM change_log
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
    today = __log_today_date()
    yesterday = __log_yesterday_date()
    groups: Dict[Any, List[str]] = {}
    other_order: List[str] = []
    for r in rows:
        user_id = (r.get("user_id") or "?").strip()
        id_p = r.get("id_produktu") or 0
        field = (r.get("field_name") or "").strip()
        val = (r.get("new_value") or "").strip()
        d = r.get("d") or ""
        t = r.get("t") or ""
        line = f"{user_id}, rekord {id_p}, pole {field}, wartość: {val}. {d} {t}"
        dt = r.get("dt")
        if dt == today:
            label = "dziś"
        elif dt == yesterday:
            label = "wczoraj"
        else:
            label = d
        if label not in groups:
            groups[label] = []
            if label not in ("dziś", "wczoraj"):
                other_order.append(label)
        groups[label].append(line)
    result = []
    for label in ["dziś", "wczoraj"]:
        if label in groups:
            result.append({"date_label": label, "entries": groups[label]})
    for label in other_order:
        result.append({"date_label": label, "entries": groups[label]})
    return result


def __log_today_date():
    from datetime import datetime
    import zoneinfo
    return datetime.now(zoneinfo.ZoneInfo("Europe/Warsaw")).date()


def __log_yesterday_date():
    from datetime import timedelta
    return __log_today_date() - timedelta(days=1)


def _row_to_product(row: Dict[str, Any]) -> Dict[str, Any]:
    """Konwertuje wiersz z DB (z kluczem id) na słownik produktu jak z JSON."""
    out = {}
    for k in PRODUCT_KEYS:
        v = row.get(k)
        if v is not None and k in NUMERIC_KEYS:
            try:
                v = float(v) if "." in str(v) or "e" in str(v).lower() else int(float(v))
            except (ValueError, TypeError):
                pass
        out[k] = v
    out["id"] = row["id"]
    out["source"] = row.get("source") or "json"
    return out


def get_all_products(conn) -> List[Dict[str, Any]]:
    """Pobiera wszystkie produkty z bazy (z kluczem id i source)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cols = ", ".join(f'"{k}"' for k in ["id", "source"] + PRODUCT_KEYS)
        cur.execute(f"SELECT {cols} FROM products ORDER BY id")
        rows = cur.fetchall()
    return [_row_to_product(dict(r)) for r in rows]


def insert_products(conn, products: List[Dict[str, Any]], source: str = "json") -> int:
    """Wstawia listę produktów. source: 'json' lub 'xml'. Zwraca liczbę wstawionych."""
    if not products:
        return 0
    cols = ["source"] + PRODUCT_KEYS
    placeholders = ", ".join("%s" for _ in cols)
    col_names = ", ".join(f'"{c}"' for c in cols)
    sql = f"INSERT INTO products ({col_names}) VALUES ({placeholders})"
    with conn.cursor() as cur:
        for p in products:
            # Pozwól nadpisać źródło na poziomie rekordu (np. mieszany import JSON + XML)
            per_row_source = (p.get("Zrodlo_danych") or p.get("source") or source or "json")
            row = [per_row_source]
            for k in PRODUCT_KEYS:
                v = p.get(k)
                if v is None and k in NUMERIC_KEYS:
                    row.append(None)
                elif k in NUMERIC_KEYS:
                    try:
                        row.append(float(v) if isinstance(v, (int, float)) else float(str(v).replace(",", ".")))
                    except (ValueError, TypeError):
                        row.append(None)
                else:
                    row.append(str(v).strip() if v is not None else None)
            cur.execute(sql, row)
        return len(products)


def update_product(conn, product_id: int, field: str, value: Any) -> bool:
    """Aktualizuje jedno pole produktu po id (PK)."""
    if field not in PRODUCT_KEYS or field == "ID_produktu":
        return False
    if field in NUMERIC_KEYS and value is not None:
        try:
            value = float(value) if isinstance(value, (int, float)) else float(str(value).replace(",", "."))
        except (ValueError, TypeError):
            value = None
    else:
        value = str(value).strip() if value is not None else None
    with conn.cursor() as cur:
        cur.execute(f'UPDATE products SET "{field}" = %s WHERE id = %s', (value, product_id))
        return cur.rowcount > 0


def delete_products_by_ids(conn, ids: List[int]) -> int:
    """Usuwa produkty o podanych id (PK). Zwraca liczbę usuniętych."""
    if not ids:
        return 0
    with conn.cursor() as cur:
        cur.execute("DELETE FROM products WHERE id = ANY(%s)", (ids,))
        return cur.rowcount


def batch_update_products(conn, ids: List[int], field: str, value: Any) -> int:
    """Ustawia pole field na value dla produktów o id z listy. Zwraca liczbę zaktualizowanych."""
    if not ids or field not in PRODUCT_KEYS or field == "ID_produktu":
        return 0
    if field in NUMERIC_KEYS and value is not None:
        try:
            value = float(value) if isinstance(value, (int, float)) else float(str(value).replace(",", "."))
        except (ValueError, TypeError):
            value = None
    else:
        value = str(value).strip() if value is not None else None
    with conn.cursor() as cur:
        cur.execute(f'UPDATE products SET "{field}" = %s WHERE id = ANY(%s)', (value, ids))
        return cur.rowcount


def clear_products(conn) -> int:
    """Usuwa wszystkie rekordy z tabeli products. Zwraca liczbę usuniętych."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM products")
        return cur.rowcount
