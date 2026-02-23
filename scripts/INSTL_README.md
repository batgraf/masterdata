# Instalprojekt – uzupełnianie EAN, wagi, wymiarów z plików producenta

## Co przejrzano

### instl_calosc.xlsx
- **Arkusz:** „Stan magazynowy” (ok. 472 wiersze, nagłówki w wierszu 1, dane od wiersza 2).
- **Kolumny:** Nazwa (3), Numer katalogowy/indeks (4), Nazwa produktu oraz EAN (5), Szerokość [mm] (14), Wysokość [mm] (15), Głębokość [mm] (16), Waga netto [kg] (17), Numer EAN (26).
- **Wynik:** 401 pozycji z indeksem, 387 z wypełnionym EAN. Wymiary i waga w mm/kg.

### cennik_instalprojekt.xlsx
- **Status:** Nie odczytany (Permission denied – plik prawdopodobnie otwarty w Excelu).
- **Propozycja:** Zamknij plik w Excelu i uruchom ponownie ekstrakcję albo skopiuj arkusz do `instl_calosc.xlsx` jeśli struktura jest taka sama.

---

## Rozwiązanie krok po kroku

### 1. Zebranie listy z Excela (gotowe)

```bash
python scripts/instl_calosc_to_list.py
```

Opcjonalnie z innym plikiem i ścieżką wyjścia:

```bash
python scripts/instl_calosc_to_list.py "C:\...\BAZY_Producent\instl_calosc.xlsx" --output scripts/instl_lista.json
```

**Wynik:** `scripts/instl_lista.json` – lista obiektów z polami: `indeks`, `EAN`, `Nazwa`, `Szerokosc_mm`, `Wysokosc_mm`, `Glebokosc_mm`, `Waga_kg`, `Wymiary` (tekst „Szer x Wys x Gleb”).

### 2. Dopasowanie do bazy Masterdata

W Twojej bazie produkty Instalprojekt mają np. pole **Nazwa_producenta** = „INSTAL PROJEKT” / „Instalprojekt” (sprawdź dokładną wartość). Dopasowanie:

- **Najpierw po SKU:** jeśli w bazie jest **SKU** = indeks z cennika (np. `AFRN2-160/13C31`) – traktuj jako ten sam produkt.
- **Gdy brak SKU lub brak dopasowania:** dopasowanie **po nazwie** (znormalizowana: małe litery, bez podwójnych spacji; ewentualnie porównanie „zawiera” / podobieństwo).

Dla każdego dopasowania:
- jeśli w bazie **EAN** jest puste → uzupełnij z listy (`EAN` z JSON),
- jeśli **Waga_brutto** puste → uzupełnij `Waga_kg` (w tej samej jednostce),
- jeśli **Szerokosc**/Wysokosc/Dlugosc puste → uzupełnij z `Szerokosc_mm`, `Wysokosc_mm`, `Glebokosc_mm` (albo jeden tekst **Wymiary** w jednym polu, zależnie od struktury bazy).

### 3. Czy da się zrobić bez błędów?

- **Tak, jeśli:**
  - dopasowanie po **indeksie/SKU** (najpewniejsze),
  - uzupełniasz **tylko puste** pola (nie nadpisujesz istniejących EAN/wag/wymiarów),
  - przed masową aktualizacją robisz **backup** (np. „zrób kopię” w Masterdata).
- **Ryzyko:** dopasowanie tylko po nazwie – możliwe pomyłki; warto ograniczyć do „wysoka podobieństwo” lub ręcznego zatwierdzenia.

---

## Następny krok (do wdrożenia w Masterdata lub skryptem)

1. Wczytać `instl_lista.json`.
2. Pobrać z bazy produkty z **Nazwa_producenta** = Instalprojekt (jedna, ustalona nazwa).
3. Dla każdego produktu z bazy: szukać w liście po **SKU** = `indeks`; jeśli brak – po **Nazwa** (znormalizowana).
4. Dla znalezionego rekordu z listy: jeśli w bazie EAN/waga/wymiary puste – zapisać propozycję (np. do pliku „propozycje_instl.json” lub ekranu podglądu).
5. Po zatwierdzeniu: wykonać aktualizację tylko pustych pól (EAN, Waga_brutto, Szerokosc, Wysokosc, Dlugosc) i zrobić backup przed zapisem.

Jeśli chcesz, można dodać w Masterdata przycisk „Uzupełnij z listy producenta” (upload JSON + wybór producenta + podgląd + Zastosuj) – wtedy całość w jednym miejscu.
