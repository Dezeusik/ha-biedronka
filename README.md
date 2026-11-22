# Biedronka → Home Assistant (nieoficjalna integracja e-paragonów)

Pobiera **e-paragony** z konta Moja Biedronka, z pełną listą pozycji, i udostępnia je w Home Assistant.
Korzysta z tego samego API co aplikacja mobilna Biedronki (`api.prod.biedronka.cloud`).
Opis API pochodzi z projektu [Rei-x/biedronka-client](https://github.com/Rei-x/biedronka-client).

> Projekt prywatny, niezwiązany z Jeronimo Martins Polska. Używaj tylko z własnym kontem.

## Instalacja
HACS → ⋮ → *Custom repositories* → `https://github.com/Dezeusik/ha-biedronka` (Integration) → pobierz →
restart → Ustawienia → Urządzenia i usługi → Dodaj integrację → **Biedronka**.

### Logowanie
Logowanie do Biedronki jest chronione przed botami, więc HA nie loguje się sam. Logujesz się raz w przeglądarce,
a integracja dostaje token odświeżania i sama go przedłuża:
1. Otwórz konsolę Chrome (Cmd+Option+J).
2. Kliknij link z okna konfiguracji i zaloguj się numerem telefonu i SMS-em.
3. Skopiuj z konsoli komunikat `Failed to launch 'app://cma20.biedronka.pl?...code=...'` i wklej go do formularza w ciągu minuty.

Gdy sesja wygaśnie, HA poprosi o ponowne logowanie (Naprawy / Repairs).

## Encje
- **Ostatni paragon** (zł; data, pozycje, grupy, kategorie budżetu)
- **Ostatnie zakupy** (czas)
- **Wydatki w tym miesiącu** / **w poprzednim miesiącu** (zł; podział na grupy i kategorie)
- **Zakupy w tym miesiącu** (liczba paragonów)
- **Najwięcej na** (grupa z największym wydatkiem w miesiącu; atrybuty = wszystkie grupy)

Grupy: Jedzenie, Słodycze i przekąski, Napoje, Alkohol, Chemia i higiena, Apteka i zdrowie, Zabawki i prezenty,
Szkoła i biuro, Ubrania, Dom i narzędzia, Dla zwierząt, Papierosy, Kaucja, Torby (`categories.py`).

## Zdarzenie
`biedronka_paragon` – każdy nowy paragon: `id`, `data`, `suma`, `sklep`, `pozycje`, `grupy`, `kategorie`,
`podsumowanie` (np. „187.40 zł → Jedzenie 120, Chemia i higiena 41, Słodycze i przekąski 26”).
Przy pierwszym uruchomieniu integracja pobiera historię bez wysyłania zdarzeń.
