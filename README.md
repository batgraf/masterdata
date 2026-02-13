# Master Data Management System

System zarządzania danymi produktów z funkcjami:
- Przeglądanie i edycja produktów
- Masowa edycja rekordów
- Filtrowanie i wyszukiwanie
- Zapisywanie widoków kolumn
- System backupu i wersjonowania

## Wersja

Aktualna wersja: **1.0.0**

## Instalacja

1. Zainstaluj zależności:
```bash
pip install -r requirements.txt
```

2. Uruchom aplikację:
```bash
python app.py
```

3. Otwórz przeglądarkę: http://127.0.0.1:5000

## Backup i wersjonowanie

- **"zrób kopię"** - tworzy backup lokalny i zwiększa patch version (1.0.0 → 1.0.1)
- **"wersja stabilna"** - tworzy backup, tag Git i automatycznie pushuje na GitHub

## Struktura projektu

```
MASTER2/
├── app.py                 # Główna aplikacja Flask
├── backup.py              # System backupu
├── VERSION.txt            # Aktualna wersja
├── requirements.txt       # Zależności Python
├── templates/             # Szablony HTML
├── static/                # Pliki statyczne
├── column_views/          # Zapisane widoki kolumn
└── backups/               # Lokalne kopie backupów
```

## Licencja

Prywatne użycie.
