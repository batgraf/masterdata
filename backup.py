"""
System backupu i wersjonowania dla Master Data.
Komendy:
- "zrób kopię" - tworzy backup do katalogu backups/
- "wersja stabilna" - tworzy tag Git i backup pełny
"""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
BACKUPS_DIR = BASE_DIR / "backups"
VERSION_FILE = BASE_DIR / "VERSION.txt"

# Pliki i katalogi do backupu
FILES_TO_BACKUP = [
    "app.py",
    "requirements.txt",
    "VERSION.txt",
    "backup.py",
]

DIRS_TO_BACKUP = [
    "templates",
    "static",
    "column_views",
]

DATA_FILES = [
    "AsortymentyMasterData.json",
    "stats.json",
]


def read_version() -> str:
    """Czyta aktualną wersję z pliku VERSION.txt"""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "1.0.0"


def increment_version(version: str, patch: bool = True) -> str:
    """Zwiększa numer wersji (major.minor.patch)"""
    parts = version.split(".")
    if len(parts) != 3:
        return "1.0.0"
    
    major, minor, patch_num = map(int, parts)
    if patch:
        patch_num += 1
    else:
        minor += 1
        patch_num = 0
    
    return f"{major}.{minor}.{patch_num}"


def create_backup(version: Optional[str] = None, stable: bool = False) -> Path:
    """
    Tworzy backup do katalogu backups/.
    
    Args:
        version: Wersja do użycia (jeśli None, używa aktualnej + zwiększa)
        stable: Czy to wersja stabilna (zwiększa minor zamiast patch)
    
    Returns:
        Ścieżka do utworzonego katalogu backupu
    """
    BACKUPS_DIR.mkdir(exist_ok=True)
    
    current_version = read_version()
    if version is None:
        new_version = increment_version(current_version, patch=not stable)
    else:
        new_version = version
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"v{new_version}_{timestamp}"
    if stable:
        backup_name = f"stable_{backup_name}"
    
    backup_path = BACKUPS_DIR / backup_name
    backup_path.mkdir(exist_ok=True)
    
    # Kopiuj pliki
    for file_name in FILES_TO_BACKUP:
        src = BASE_DIR / file_name
        if src.exists():
            shutil.copy2(src, backup_path / file_name)
    
    # Kopiuj katalogi
    for dir_name in DIRS_TO_BACKUP:
        src = BASE_DIR / dir_name
        if src.exists() and src.is_dir():
            shutil.copytree(src, backup_path / dir_name, dirs_exist_ok=True)
    
    # Kopiuj pliki danych
    for file_name in DATA_FILES:
        src = BASE_DIR / file_name
        if src.exists():
            shutil.copy2(src, backup_path / file_name)
    
    # Zapisz informacje o backupie
    backup_info = {
        "version": new_version,
        "timestamp": timestamp,
        "stable": stable,
        "previous_version": current_version,
    }
    (backup_path / "backup_info.json").write_text(
        json.dumps(backup_info, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    # Aktualizuj VERSION.txt jeśli to nowa wersja
    if version is None:
        VERSION_FILE.write_text(f"{new_version}\n", encoding="utf-8")
    
    return backup_path


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        try:
            if command == "kopie" or command == "kopię" or command == "backup":
                backup_path = create_backup(stable=False)
                print(f"OK Utworzono backup: {backup_path.name}", file=sys.stdout)
                sys.stdout.flush()
            elif command == "stabilna" or command == "stable":
                backup_path = create_backup(stable=True)
                print(f"OK Utworzono wersje stabilna: {backup_path.name}", file=sys.stdout)
                sys.stdout.flush()
            else:
                print(f"Nieznana komenda: {command}", file=sys.stderr)
                print("Uzyj: python backup.py kopie | stabilna", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"BLAD: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)
    else:
        print("Uzyj: python backup.py kopie | stabilna", file=sys.stderr)
        sys.exit(1)
