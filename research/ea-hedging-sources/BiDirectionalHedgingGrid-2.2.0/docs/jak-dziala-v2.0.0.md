# Jak działa bot — wersja 2.0.0

Tu zmienia się najważniejsza rzecz: **bot przestaje stawiać Take Profit na każdej pozycji**. Zamiast tego traktuje wszystkie kupna jako jeden koszyk i wszystkie sprzedaży jako drugi.

## Start

Jak wcześniej: małe kupno i mała sprzedaż naraz. Tym razem bez indywidualnego celu na zleceniu.

## Uśrednianie

Gdy cena idzie przeciwko koszykowi, bot dokłada kolejne, większe pozycje w tym samym kierunku. To nadal siatka.

## Wspólne zamknięcie koszyka

Bot liczy **średnią cenę wejścia** wszystkich pozycji w koszyku (większa pozycja ma większy wpływ).

Cel zamknięcia = ta średnia plus (albo minus) jeden krok siatki.

Gdy cena tam dojdzie, **zamyka cały koszyk naraz**. Dzięki temu dokładanie stratnych nóg naprawdę obniża poprzeczkę — nie trzeba wracać aż do pierwszej, najgorszej ceny.

Na wykresie widać poziom tego wspólnego celu: niebieska linia dla kupna, czerwona dla sprzedaży.

## Co po zysku? Rotacja stron

Po zamknięciu koszyka kupna bot **nie** otwiera od razu nowego kupna. Otwiera bazową **sprzedaż** (i odwrotnie).

To był celowy „kontr-cykl”. W praktyce jedna strona mogła znikać na dłużej, a druga pracować sama — stąd w wersji 2.1.0 z tej rotacji zrezygnowano.

## Bezpieczniki

Bez zmian: dzienny drawdown, pauza północna, weekend, filtr spreadu.
