# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Numeracja: [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

- **MAJOR** — zmiana architektury strategii (np. indywidualne TP → koszyk).
- **MINOR** — nowe usprawnienie bez łamania dotychczasowej logiki.
- **PATCH** — poprawka błędu / doprecyzowanie.

W MQL5 to samo wydanie zapisujemy jako `#property version "X.YY"` (np. `2.20` = git tag `v2.2.0`).

Opis logiki **prostym językiem** (dla użytkownika, nie programisty): folder [docs/](docs/README.md).

## [2.2.0] — 2026-08-17

### Added
- `BaseTakeProfitPoints` (domyślnie 200) — sztywny TP pojedynczej pozycji bazowej.
- Hybryda dwóch trybów: baza z TP brokera; od 2. nogi koszyk BE + `BasketProfitTarget_USD`.
- `StripBasketStops` — przy pierwszej dokładce siatki zdejmowane są TP/SL całego koszyka.
- Linie: TP bazy przy `count==1`; BE (ciągła) + Basket TP (przerywana) przy `count>=2`.

### Changed
- Domyślny cel koszyka: `BasketProfitTarget_USD = 0.5`.
- `ManageBasket` działa tylko gdy w koszyku są co najmniej 2 pozycje (bazy nie zamyka za 0.50 USD).

## [2.1.0] — 2026-08-17

### Changed
- Usunięta rotacja stron (`OpenOppositeBase`). Po zamknięciu koszyka otwierana jest nowa baza **tej samej** strony.
- BUY i SELL działają w pełni niezależnie — pusta noga nie blokuje drugiej.
- Wyjście koszyka: Break-Even + minimalny zysk `BasketProfitTarget_USD` (PnL z swapem i prowizją), a nie sztywny GridStep.
- Linia na wykresie stoi na średniej ważonej (punkt zero), nie na cenie Take Profit.

### Added
- Przeliczenie celu USD na dystans ceny z `tick size` / `tick value` (poprawne dla XAUUSD).
- Opisy działania każdej wersji w folderze `docs/` (prosty język).

## [2.0.0] — 2026-08-17

### Changed
- Usunięte indywidualne Take Profit na pojedynczych pozycjach (`SL=0`, `TP=0`).
- Koszyk BUY i SELL zamykany wspólnym Basket TP od średniej ważonej:
  `suma(cena × wolumen) / suma(wolumen) ± GridStep`.
- Po zamknięciu koszyka startuje kontr-cykl: baza strony przeciwnej zamiast tej samej.

### Added
- Linie `OBJ_HLINE` wspólnego Basket TP (niebieski BUY, czerwony SELL) na wykresie i w testerze wizualnym.

## [1.0.0] — 2026-08-17

### Added
- Pierwsza wersja: hedging Buy+Sell, siatka Fixed/ATR, soft martingale.
- Indywidualne TP na każdej pozycji, cel USD koszyka.
- Warstwa prop: daily drawdown 4.5%, pauza północna, zamknięcie weekendowe, filtr spreadu.
