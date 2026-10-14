# Bi-directional Hedging Grid EA (MQL5)

Expert Advisor dla **XAUUSD** (RoboForex) z dwukierunkową siatką hedgingową, soft-martingale i warstwą ryzyka pod wymogi firm prop.

Aktualna wersja: **2.20** (wydanie gita **v2.2.0**).

**Jak to działa, zwykłym językiem** (bez testowania w testerze):

- aktualna wersja → [docs/jak-dziala-v2.2.0.md](docs/jak-dziala-v2.2.0.md)
- spis wszystkich wersji → [docs/README.md](docs/README.md)
- lista zmian technicznych → [CHANGELOG.md](CHANGELOG.md)

Repozytorium: https://github.com/Yoshinarium/BiDirectionalHedgingGrid

Jeden plik źródłowy na wszystkie wersje: `BiDirectionalHedgingGrid.mq5` (bez `_v2` / `_v3` w nazwie). Kolejne wydania to tagi gita (`v1.0.0`, `v2.0.0`, …) i GitHub Releases.

## Instalacja

1. Skopiuj `BiDirectionalHedgingGrid.mq5` do folderu:
   `MetaTrader 5\MQL5\Experts\`
2. W MetaEditorze skompiluj (F7).
3. Uruchom na wykresie **XAUUSD** na rachunku **hedging** (nie netting).
4. Włącz AutoTrading. W logu Experts powinna pojawić się linia `HG: init XAUUSD | point=... tick=...`.

Netting zostanie odrzucony już w `OnInit()` — jednoczesny Buy i Sell nie da się utrzymać na rachunku netto.

## Specyfikacja złota (Points vs Tick)

Na XAUUSD `_Point` często **nie** jest tym samym co tick kontraktu.

| Pole brokera | Co oznacza | Typowy RoboForex XAUUSD |
|---|---|---|
| `SYMBOL_DIGITS` | Liczba miejsc po przecinku | 2 albo 3 |
| `_Point` / `SYMBOL_POINT` | Najmniejsza zmiana w notowaniu | `0.01` (2 cyfry) albo `0.001` (3 cyfry) |
| `SYMBOL_TRADE_TICK_SIZE` | Minimalny krok ceny zlecenia / TP | często `0.01` |
| `SYMBOL_TRADE_TICK_VALUE` | Wartość 1 ticka w walucie depozytu dla 1.00 lota | broker liczy sam |

**Przykład:** `FixedGridPoints = 100`

- 2 cyfry (`_Point = 0.01`) → krok siatki **1.00 USD**
- 3 cyfry (`_Point = 0.001`) → krok siatki **0.10 USD**

Sprawdź Specyfikację symbolu w Market Watch. Jeśli gold jest notowany z 3 miejscami, 100 punktów to bardzo ciasna siatka — wtedy podnieś `FixedGridPoints` (np. 1000 = 1.00 USD).

EA:

- liczy dystans jako `FixedGridPoints * _Point` albo `ATR * AtrMultiplier`
- **wyrównuje TP do `SYMBOL_TRADE_TICK_SIZE`** (inaczej `OrderSend` pada na Invalid stops)
- bierze P&L koszyka z `POSITION_PROFIT + SWAP + COMMISSION` (tick value złota liczy broker)

Spread: `(Ask - Bid) / _Point`. `MaxSpreadPoints = 30` przy 2 cyfrach to $0.30, przy 3 cyfrach $0.03.

## Logika strategii

1. **Start:** brak pozycji z magic 1000/2000 → jednocześnie 1× Buy i 1× Sell (`BaseLot`), każda z twardym TP w odległości `GetGridStep()`, bez SL.
2. **Trend (TP):** gdy **najnowsza** pozycja koszyka trafia w TP, od razu otwierana jest nowa baza `BaseLot` w tym samym kierunku.
3. **Pod prąd (martingale):** cena oddala się od ostatniego otwarcia o ≥ `GetGridStep()` → nowa pozycja, lot = `ostatni lot * LotMultiplier` (zaokrąglenie w górę o `VOLUME_STEP`, żeby siatka realnie rosła na zlocie).
4. **Koszyk:** niezależnie Buy i Sell. Gdy suma floating P&L ≥ `BasketProfitTarget_USD` → zamknięcie całego koszyka (iteracja od końca) i od razu nowa pozycja startowa, żeby hedge wrócił.

## Warstwa prop

| Mechanizm | Zachowanie |
|---|---|
| Daily drawdown | Equity z 00:00 czasu serwera. Jeśli `((SOD - Equity) / SOD) * 100 >= 4.5%` → zamyka nasze pozycje, kasuje pending, blokuje handel do następnego 00:00. Stan trzyma się w Global Variables (przeżywa restart terminala). |
| Midnight pause | 23:55–00:15: **brak nowych zleceń**. Zamykanie koszyków i TP na już otwartych pozycjach działa. |
| Weekend | Piątek od `FridayCloseTime` zamyka wszystko i usypia bota do poniedziałku (start sesji). |
| Spread | Nowe wejścia tylko gdy spread ≤ `MaxSpreadPoints`. |

`MaxDailyDrawdownPercent = 4.5` zostawia bufor względem typowego limitu 5% u propów. Dostosuj do regulaminu konkretnej firmy (equity vs balance, trailing vs daily).

Domyślnie EA zamyka **tylko swoje** magic numbers — nie rusza innych robotów na tym samym koncie.

## Inputy

Sekcje w oknie EA odpowiadają grupom w kodzie. Parametry ryzyka są `sinput` (nie wchodzą do optymalizatora testera).

Po restarcie EA odczytuje istniejące pozycje i wznawia siatkę od najnowszej w każdym koszyku.

## Tester / live

- W Strategy Testerze włącz model ticków możliwie bliski realnym (złoto ma szeroki spread na rolloverze).
- Hedging grid + martingale **potrafi szybko zjeść depozyt** przy trendzie jednokierunkowym — daily DD jest hamulcem, nie gwarancją.
- Przed live: demo na tym samym typie konta RoboForex (ECN vs Pro), sprawdź filling (IOC/FOK), prowizję i `VOLUME_STEP`.
