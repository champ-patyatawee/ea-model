# Jak działa bot — wersja 1.0.0

To pierwsza wersja. Najłatwiej myśleć o niej jak o **dwóch osobnych siatkach**: jedna kupuje, druga sprzedaje.

## Start

Bot od razu otwiera dwie małe pozycje:

- 1× **kupno** (BUY)
- 1× **sprzedaż** (SELL)

Każda dostaje własny cel zysku (Take Profit) w stałej odległości. Stop Loss na pojedynczej pozycji nie ma.

## Gdy rynek idzie „z Tobą”

Jeśli cena idzie w górę, pozycja kupna może trafić w swój Take Profit i znika. Bot od razu stawia **nowe, małe kupno**. Analogicznie przy spadku — z pozycją sprzedaży.

## Gdy rynek idzie „przeciwko Tobie”

Jeśli cena oddala się od ostatniej pozycji o kolejny krok siatki, bot dokłada następną w tym samym kierunku. Każda kolejna jest trochę większa (łagodny martingale). Też dostaje **własny**, osobny Take Profit.

Tu jest główna słabość tej wersji: stratne pozycje nie „ściągają się” do wspólnego zera. Każda nogą goni swój własny cel, więc koszyk może długo wisieć w stracie.

## Dodatkowe zamknięcie

Jeśli cały koszyk kupna albo sprzedaży uzbiera ustawiony zysk w dolarach, bot zamyka **wszystkie** pozycje tej strony i stawia nową bazową.

## Bezpieczniki (są też w nowszych wersjach)

- dzienny limit obsunięcia kapitału
- pauza koło północy (rollover)
- zamknięcie w piątek przed weekendem
- zakaz nowych wejść przy zbyt szerokim spreadzie
