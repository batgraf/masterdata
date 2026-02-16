# Master Data – gdzie skończyliśmy (na jutro)

**Data:** 14.02.2025

---

## Co zrobiliśmy dziś

1. **Kolumna „Tryb”** (wcześniej „Status”) – druga kolumna w tabeli.
   - Wartości: **nowe**, **w trakcie**, **gotowe**.
   - Backend: pole `Tryb` w `PRODUCT_KEYS` (db.py, app.py), kolumna w PostgreSQL (rename z „Status” na „Tryb”).

2. **UI trybu – pigułka zamiast listy rozwijanej**
   - Komórka to **kolorowy przycisk (pill)**; po kliknięciu rozwijają się 3 kolorowe opcje.
   - Kolory: nowe = `#deedff`, w trakcie = `#fffca3`, gotowe = `#d4fec9`.
   - Zmiana trybu: klik w pigułkę → wybór z listy → zapis (PATCH). Bez kreski „—”, domyślnie „nowe”.

3. **Kolor całego wiersza** według trybu – wiersz ma tło w kolorze wybranej pigułki.

4. **Masowa edycja** – w modalu „Edytuj” przy wyborze pola **Tryb** pole „Wartość” to lista rozwijana z trzema statusami.

5. **Widok kolumn i filtry** – przycisk Tryb w toolbarze, opcja Tryb w kryteriach (puste/nie puste).

---

## Stan na koniec dnia

- Aplikacja działa z PostgreSQL i kolumną Tryb.
- Restart: `sudo systemctl restart masterdata.service`.
- Pliki: `app.py`, `db.py`, `templates/index.html`, `data_loaders.py` (bez zmian dla Tryb).

---

## Co robimy dalej – plan (od tego zaczynamy)

**Zaczynamy od otwarcia tego pliku** – potem kolejno:

1. **Paginacja** – nawigacja „do początku” ◀◀ i „do ostatniej” ▶▶ (pierwsza / ostatnia strona).
2. **Sortowanie kolumn** – klik w nagłówek kolumny = sortowanie po tej kolumnie (rosnąco/malejąco).
3. **Wybór ilości wyświetlanych rekordów** – np. 50 / 100 / 200 / 500 na stronę.
4. **Błąd w modalu „Kryteria” (opcje)** – lista kolumn w „kolumna” (puste / nie puste) **nie pokazuje wszystkich możliwych kolumn** – trzeba to naprawić.

Dalszy rozwój według **PLAN_źródła_danych.md** (CSV, kolejne źródła itd.) – po powyższych punktach.

---

## Jak kontynuować jutro

Otwórz **STATUS_na_jutro.md** i napisz asystentowi:  
*„Kontynuujemy masterdata – stan w STATUS_na_jutro.md, zaczynamy od punktów 1–4 z planu.”*
