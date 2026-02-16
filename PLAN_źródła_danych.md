# Plan: wiele źródeł danych (JSON, XML, CSV) w Master Data

**Cel:** Umożliwić ładowanie produktów nie tylko z pliku JSON, ale też z XML lub CSV (w tym duże pliki ~11 tys. produktów).

---

## Wdrożone (PostgreSQL + upload JSON/XML)

- **PostgreSQL:** gdy ustawiony `DATABASE_URL`, dane są w tabeli `products` (plik `db.py`, inicjalizacja przy starcie).
- **Upload:** przy DB – akceptowane pliki **.json** i **.xml**; import do bazy z polem `source` (json/xml). Bez DB – jak dotąd tylko .json nadpisuje plik.
- **Loader XML:** `data_loaders.py` – mapowanie suuhouse (Nr_katalogowy→SKU, Nazwa_produktu→Nazwa, Kod_ean→EAN, Producent→Nazwa_producenta itd.).
- **Eksport:** Pobierz bazę → JSON w tej samej strukturze kolumn co wejściowy (bez pól `id`/`source`).
- **Duplikaty:** `GET /api/duplicates?by=ean` lub `?by=sku` – raport wartości występujących więcej niż raz.
- **Konfiguracja:** `.env.example` z opisem `DATABASE_URL`. Zależność: `psycopg2-binary` w `requirements.txt`.

---

## 1. Stan obecny

- **Źródło:** jeden plik `AsortymentyMasterData.json`.
- **Ładowanie:** `load_products()` w `app.py` – odczyt JSON, cache po `mtime`.
- **Zapis:** kilka miejsc zapisuje do tego samego pliku JSON (m.in. po edycji, upload, clear).
- **Struktura produktu:** słownik z kluczami po polsku, np. `ID_produktu`, `Nazwa`, `EAN`, `Nazwa_producenta`, `Waga_brutto`, `Cena_sprzedazy_brutto` itd.

Cała aplikacja zakłada, że dane to **lista słowników** o spójnym zestawie pól.

---

## 2. Co trzeba ustalić przed wdrożeniem

### 2.1 Źródła

- **JSON** – obecny format (mebloszyk).
- **XML** – np. eksport typu suuhouse (struktura np. `<Produkt>` z polami: `Id_produktu`, `Nr_katalogowy`, `Nazwa_produktu`, `Kod_ean`, `Producent`, `Cena_brutto` itd. – **nazwy pól inne niż w JSON**). Struktura przejrzana – patrz sekcja 2a poniżej.
- **CSV** – format do ustalenia (rozdzielnik, nagłówek, kodowanie).

Trzeba mieć **konkretne przykłady** plików XML i CSV (nagłówki / kilka wierszy), żeby zaprojektować mapowanie.

### 2a. Struktura XML suuhouse (przejrzana)

**URL:** `https://www.suuhouse.pl/export/master.xml`

| Parametr | Wartość |
|----------|---------|
| Rozmiar pliku | ~7,8 MB |
| Liczba produktów | **8 895** |
| Kodowanie | UTF-8 |
| Root | `<Produkty>` |
| Element produktu | `<Produkt>` |

**Wszystkie tagi w pliku (alfabetycznie):**  
`Cena_brutto`, `Cena_katalogowa` (opcjonalny), `Cena_netto`, `Cena_zakupu`, `Dostepnosc`, `Id_produktu`, `Ilosc_produktow`, `Jednostka_miary`, `Jednostka_rozmiaru` (opcjonalny), `Kategorie_id`, `Kod_ean`, `Kod_producenta`, `Krotka_nazwa_produktu` (opcjonalny), `Nazwa_produktu`, `Nr_katalogowy`, `Nr_referencyjny_1` (opcjonalny), `Nr_referencyjny_2` (opcjonalny), `Producent`, `Rozmiar_pojemnosc`, `Waga`. Wartości tekstowe często w `<![CDATA[...]]>`.

**Proponowane mapowanie XML suuhouse → format wewnętrzny (JSON mebloszyk):**

| XML (suuhouse) | Wewnętrzny (obecny JSON) |
|----------------|---------------------------|
| `Id_produktu` | `ID_produktu` |
| `Nr_katalogowy` | `SKU` |
| `Nazwa_produktu` | `Nazwa` |
| `Kod_ean` | `EAN` |
| `Producent` | `Nazwa_producenta` |
| `Waga` | `Waga_brutto` |
| `Cena_brutto` | `Cena_sprzedazy_brutto` |
| `Cena_netto` | `Cena_sprzedazy_netto` |
| `Cena_zakupu` | np. `Cena_zakupu_brutto` |
| `Ilosc_produktow` | np. `Stan_magazynowy` |
| `Jednostka_miary` | `JM_sprzedazy` |
| `Dostepnosc` | `Dostepnosc` (tekst) |
| `Kategorie_id` | brak w JSON – dodać lub ignorować |
| `Rozmiar_pojemnosc` | opcjonalnie pole tekstowe |

Pola w JSON, których **nie ma** w XML suuhouse: `Status_produktu`, `URL_Miniatura`, `Rodzaj_produktu`, `Grupa_produktu`, wymiary, `ID_producenta`, `Rezerwacja` itd. – przy ładowaniu z XML uzupełniać pustymi wartościami / `None`.

### 2.2 Tryb „tylko odczyt” vs „odczyt i zapis”

- **Opcja A – tylko odczyt z XML/CSV**  
  Ładowanie z XML/CSV do podglądu/analizy. Edycja i zapis tylko do JSON (np. „Zapisz jako JSON” / „Użyj jako bieżącą bazę” → zapis do `AsortymentyMasterData.json`).

- **Opcja B – pełna obsługa**  
  Zapis także do XML/CSV (wymaga ustalenia szablonu XML i formatu CSV oraz zasad aktualizacji plików).

**Rekomendacja na start:** Opcja A – mniej zależności, mniejsze ryzyko, wystarczy do „pobierania produktów z XML/CSV”.

### 2.3 Gdzie wybiera się źródło

Możliwe podejścia:

- **Konfiguracja (plik / zmienna środowiska):** ścieżka do pliku + typ (json/xml/csv). Po zmianie konfiguracji restart lub przeładowanie.
- **UI:** wybór „Źródło danych” (np. listą: bieżący JSON / plik XML / plik CSV / upload). Wymaga endpointów do ustawiania źródła i ewentualnie uploadu XML/CSV.
- **Upload „załaduj i używaj”:** użytkownik wgrywa XML lub CSV, backend konwertuje do wewnętrznego formatu i np. zapisuje do JSON albo trzyma w pamięci/cache do czasu wyboru innego źródła.

Do planu warto dopisać, czy źródło ma być **jedno globalne** (cała aplikacja z jednego pliku), czy w przyszłości **wiele źródeł** (np. osobne widoki/tabele dla różnych plików).

---

## 3. Architektura (propozycja)

### 3.1 Warstwa abstrakcji „źródło danych”

- **Jeden punkt wejścia:** np. `load_products()` dalej zwraca `list[dict]` (produkty w ujednoliconym formacie).
- **Pod spodem:** wybór źródła (config/UI):
  - `json` → obecna logika (plik JSON).
  - `xml` → nowy loader: ścieżka/URL do XML, parsowanie (streaming przy ~11k produktów).
  - `csv` → nowy loader: ścieżka do CSV, odczyt z nagłówkiem, mapowanie kolumn.

Cache (np. po `mtime`/ścieżce) można rozszerzyć tak, żeby klucz zawierał **typ źródła + ścieżkę**.

### 3.2 Mapowanie pól (XML/CSV → wewnętrzny format)

- Zdefiniować **wewnętrzny zestaw pól** (np. taki jak dziś w JSON: `ID_produktu`, `Nazwa`, `EAN`, `Nazwa_producenta` itd.).
- Dla każdego zewnętrznego formatu (XML suuhouse, CSV…) mieć **słownik mapowania**:  
  `nazwa_w_xml/csv` → `nazwa_wewnętrzna`.
- Pola brakujące w źródle: wypełniać `None` lub `""`.  
Opcjonalnie: osobne mapowania per „profil” (np. `suuhouse_xml`, `nasz_csv`).

Mapowania trzymać w konfiguracji lub w osobnym module (np. `data_mappings.py`), żeby dodanie nowego formatu nie mieszało logiki ładowania.

### 3.3 Wydajność (duży XML ~11k produktów)

- **XML:** parsowanie strumieniowe (np. `xml.etree.ElementTree` iterparse lub `lxml`) zamiast wczytania całego pliku do pamięci.
- **CSV:** odczyt linia po linii (standardowy `csv.reader`), bez wczytania całego pliku do stringa.
- **Cache:** po pierwszym wczytaniu trzymać listę w pamięci (jak teraz); przy następnych żądaniach zwracać z cache do momentu zmiany pliku/konfiguracji.

Dla bardzo dużych plików można w przyszłości rozważyć paginację po stronie backendu, ale na start wystarczy „wczytaj wszystko → cache → serwuj”.

---

## 4. Kroki wdrożenia (gdy będzie decyzja „robimy”)

1. **Zebrać przykłady:** 1 plik XML (np. suuhouse), 1 plik CSV – ustalić dokładną strukturę i kodowanie.
2. **Zdefiniować mapowania:** tabela XML→wewnętrzne, CSV→wewnętrzne (plus obsługa brakujących pól).
3. **Dodać loadery:**  
   - `load_from_json(path)` (obecna logika),  
   - `load_from_xml(path_or_url)` (streaming),  
   - `load_from_csv(path)`.
4. **Abstrakcja źródła:** config/zmienna „current source” (typ + ścieżka). `load_products()` wywołuje odpowiedni loader i zwraca listę w wewnętrznym formacie.
5. **Cache:** rozszerzyć o (typ, ścieżka, mtime/etag) zamiast tylko `DATA_FILE` + `mtime`.
6. **Zapis:**  
   - przy źródle JSON – bez zmian (zapis do tego samego pliku);  
   - przy XML/CSV – tylko eksport/„Zapisz jako JSON” lub „Ustaw jako bieżącą bazę” (zapis do JSON), bez zapisu z powrotem do XML/CSV (o ile wybierzemy Opcję A).
7. **UI/API:**  
   - wybór źródła (lista + ewentualnie upload pliku),  
   - endpoint do ustawiania źródła (np. typ + ścieżka lub ID uploadu),  
   - w upload rozszerzyć akceptowane rozszerzenia o `.xml`, `.csv` i po konwersji zapisać do JSON albo ustawić jako bieżące źródło w pamięci.

---

## 5. Podsumowanie

| Aspekt | Propozycja |
|--------|------------|
| Źródła | JSON (obecne) + XML + CSV |
| Format wewnętrzny | Bez zmian – lista dictów z ustalonymi kluczami |
| Mapowanie | Słowniki nazwa_zewnętrzna → nazwa_wewnętrzna per format |
| Zapis przy XML/CSV | Tylko „do JSON” / „jako bieżąca baza” (Opcja A) |
| Duże pliki | Parsowanie strumieniowe (XML/CSV), cache w pamięci |
| Konfiguracja źródła | Do ustalenia: plik config vs UI (lista + upload) |

Jak ustalisz: **konkretne formaty XML/CSV**, **czy tylko odczyt z XML/CSV (Opcja A)** oraz **skąd użytkownik wybiera źródło (config vs UI)** – można doprecyzować ten plan (np. konkretne nazwy pól w mapowaniach) i dopiero wtedy wchodzić w implementację.

---

## 6. Model: źródło → praca → wynik (ustalony)

- **Baza źródłowa** – składa się z JSON + XML: użytkownik ładuje oba (kolejność: XML traktowany jako master), merge + deduplikacja/scalanie → jedna baza w systemie (np. PostgreSQL). **Nadpisuje** to, co było wcześniej (na czysto = wyzerować i wgrać od nowa).
- **Praca** – prowadzona na **kopii** źródła: edycje, usuwanie zbędnych rekordów, wielokrotne wracanie. Źródło pozostaje nietknięte.
- **Zapis kopii użytkownika** – „Zapisz moją bieżącą bazę” = zapis stanu bazy jako kopia przypisana do usera. **3 wersje z datą/czasem** (np. 3 ostatnie zapisy), nie jeden slot.
- **Wczytanie bazy usera** – wczytanie zapisanej kopii (lub pliku od innego) żeby kontynuować pracę.
- **Wynik** – osobna akcja: **pobierz gotową bazę do pliku JSON** (eksport).

---

## 7. Deduplikacja i scalanie (plan)

### 7.1 Kiedy uznajemy „ten sam produkt” (dopasowanie)

- **Kolejność sprawdzania:** najpierw sztywne klucze, nazwa tylko gdy brak tych pól.
- **Reguły (OR):**
  - **ID** identyczne,
  - **SKU** identyczne – gdy oba rekordy mają niepuste SKU,
  - **EAN** identyczne – gdy oba rekordy mają niepuste EAN,
  - **Nazwa** bardzo podobna (po normalizacji) – gdy brak pewnego dopasowania po ID/SKU/EAN.

### 7.2 Kto jest bazą, kto uzupełnia

- **XML = master** (baza ze sklepu, pilnowana). **JSON uzupełnia.**
- W praktyce: rekord **bazowy** pochodzi z XML; pola puste w XML uzupełniamy z JSON.
- **Konflikt** (oba źródła mają wypełnione to samo pole, różne wartości): **XML wygrywa.**

### 7.3 Scalanie

- **Dopasowana para** (ten sam produkt w JSON i XML) → **jeden rekord**: baza z XML, uzupełnienie pustych pól z JSON; przy konflikcie wartość z XML.
- **Rekord tylko w jednym źródle** (tylko JSON lub tylko XML) → trafia do wyniku jako jeden rekord (brak pary do scalenia).
- Przykład: rekord A (XML) ma SKU, nazwę, ID; rekord B (JSON) ma EAN, ID, nazwę → wynik: jeden rekord A z dopisanym EAN z B.

### 7.4 Opcjonalnie w przyszłości

- **Wybór strategii** scalania: np. „więcej wypełnionych pól” lub „nowsza data modyfikacji” jako alternatywa do „merge + XML master”. Na start: **domyślnie merge + XML master.**
