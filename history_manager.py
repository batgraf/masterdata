"""
System zarządzania historią zmian (undo/redo) dla Master Data.
Każdy użytkownik ma własną historię do 20 kroków wstecz.
"""
import json
import gzip
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent
HISTORY_DIR = BASE_DIR / "history"
MAX_HISTORY_STEPS = 20


def get_user_history_dir(user_id: str) -> Path:
    """Zwraca katalog historii dla danego użytkownika."""
    safe_user = "".join(ch for ch in user_id.strip() if ch.isalnum() or ch in ("_", "-"))
    if not safe_user:
        safe_user = "anonymous"
    user_dir = HISTORY_DIR / safe_user
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def save_snapshot(user_id: str, products: List[Dict[str, Any]], action: str = "edit") -> Optional[str]:
    """
    Zapisuje snapshot przed zmianą.
    
    Args:
        user_id: Identyfikator użytkownika
        products: Lista produktów do zapisania
        action: Typ akcji (edit, batch_edit, delete, etc.)
    
    Returns:
        ID snapshotu lub None jeśli błąd
    """
    try:
        user_dir = get_user_history_dir(user_id)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        snapshot_id = f"snapshot_{timestamp}"
        snapshot_file = user_dir / f"{snapshot_id}.json.gz"
        
        # Zapisz skompresowany snapshot
        snapshot_data = {
            "timestamp": timestamp,
            "action": action,
            "products": products,
        }
        
        with gzip.open(snapshot_file, "wt", encoding="utf-8") as f:
            json.dump(snapshot_data, f, ensure_ascii=False, indent=2)
        
        # Ogranicz do MAX_HISTORY_STEPS
        cleanup_old_snapshots(user_id)
        
        return snapshot_id
    except Exception as e:
        print(f"Błąd zapisu snapshotu: {e}")
        return None


def load_snapshot(user_id: str, snapshot_id: str) -> Optional[List[Dict[str, Any]]]:
    """
    Wczytuje snapshot.
    
    Args:
        user_id: Identyfikator użytkownika
        snapshot_id: ID snapshotu
    
    Returns:
        Lista produktów lub None jeśli błąd
    """
    try:
        user_dir = get_user_history_dir(user_id)
        snapshot_file = user_dir / f"{snapshot_id}.json.gz"
        
        if not snapshot_file.exists():
            return None
        
        with gzip.open(snapshot_file, "rt", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("products")
    except Exception as e:
        print(f"Błąd wczytania snapshotu: {e}")
        return None


def get_history_list(user_id: str) -> List[Dict[str, Any]]:
    """
    Zwraca listę dostępnych snapshotów dla użytkownika (od najnowszego).
    
    Returns:
        Lista słowników z informacjami o snapshotach
    """
    try:
        user_dir = get_user_history_dir(user_id)
        snapshots = []
        
        for snapshot_file in sorted(user_dir.glob("snapshot_*.json.gz"), reverse=True):
            try:
                with gzip.open(snapshot_file, "rt", encoding="utf-8") as f:
                    data = json.load(f)
                    snapshots.append({
                        "id": snapshot_file.stem.replace(".json", ""),
                        "timestamp": data.get("timestamp", ""),
                        "action": data.get("action", "unknown"),
                        "formatted_time": format_timestamp(data.get("timestamp", "")),
                    })
            except Exception:
                continue
        
        return snapshots[:MAX_HISTORY_STEPS]  # Maksymalnie 20
    except Exception:
        return []


def format_timestamp(timestamp: str) -> str:
    """Formatuje timestamp do czytelnej formy."""
    try:
        dt = datetime.strptime(timestamp, "%Y-%m-%d_%H-%M-%S-%f")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return timestamp


def cleanup_old_snapshots(user_id: str) -> None:
    """Usuwa stare snapshoty, zostawiając tylko MAX_HISTORY_STEPS najnowszych."""
    try:
        user_dir = get_user_history_dir(user_id)
        snapshots = sorted(user_dir.glob("snapshot_*.json.gz"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Usuń wszystkie poza MAX_HISTORY_STEPS najnowszymi
        for snapshot_file in snapshots[MAX_HISTORY_STEPS:]:
            try:
                snapshot_file.unlink()
            except Exception:
                pass
    except Exception:
        pass


def clear_history(user_id: str) -> None:
    """Czyści całą historię użytkownika."""
    try:
        user_dir = get_user_history_dir(user_id)
        for snapshot_file in user_dir.glob("snapshot_*.json.gz"):
            try:
                snapshot_file.unlink()
            except Exception:
                pass
    except Exception:
        pass
