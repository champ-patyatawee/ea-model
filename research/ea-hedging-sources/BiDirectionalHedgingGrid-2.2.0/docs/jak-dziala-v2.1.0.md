# Jak działa bot — wersja 2.1.0 (aktualna)

Najprostszy obraz: **dwa niezależne sklepy na jednym parkiecie**.

- Sklep „kupno” zajmuje się tylko pozycjami BUY.
- Sklep „sprzedaż” zajmuje się tylko pozycjami SELL.

Nie podkradają sobie roboty. Jeśli kupno akurat zarabia i się zamyka, sprzedaż dalej może uśredniać stratę — i odwrotnie.

## 1. Start dnia / pusty wykres

Jeśli nie ma kupna — bot otwiera małe kupno.  
Jeśli nie ma sprzedaży — bot otwiera małą sprzedaż.  
Oba mogą (i zwykle powinny) wisieć jednocześnie.

## 2. Gdy cena idzie pod prąd

Przykład: masz kupno, a złoto spada.

Bot czeka, aż cena odjedzie o jeden krok siatki od **ostatniego** kupna, i dokłada kolejne, trochę większe kupno. I tak dalej.

To samo, lustrzanie, przy sprzedaży gdy cena idzie w górę.

Pojedyncze zlecenia **nie mają** Stop Loss ani Take Profit. O zamknięciu decyduje cały koszyk.

## 3. Gdzie jest „zero”? Break-even

Bot liczy średnią cenę wszystkich kupn (albo wszystkich sprzedaży), ważoną wielkością pozycji.

To jest punkt, w którym ten koszyk wychodzi na **zero** — bez zysku, bez straty z samego ruchu ceny.

Na wykresie stoi pozioma linia właśnie tam:

- niebieska = zero koszyka kupna
- czerwona = zero koszyka sprzedaży

Im więcej dokładasz niżej (przy kupnie), tym ta linia zjeżdża w dół. Nie musisz wracać do pierwszej, najdroższej ceny.

## 4. Kiedy bot zamyka zysk

Nie czeka na duży ruch od średniej. Zamyka koszyk, gdy **łącznie** (wszystkie pozycje tej strony) uzbiera ustawiony mały zysk w walucie konta — domyślnie kilka dolarów.

Ten zysk ma pokryć spread, prowizję i swap. To jest „wyjście trochę nad zerem”, nie polowanie na duży Take Profit.

Po zamknięciu bot **od razu otwiera nowe, małe zlecenie tej samej strony**. Kupno wraca jako kupno, sprzedaż jako sprzedaż. Żadnej zamiany ról.

## 5. Czego bot nie robi

- Nie zamyka kupna dlatego, że sprzedaż zarobiła (i odwrotnie).
- Nie stawia Stop Loss na pojedynczej nodze — ochroną jest dzienny limit obsunięcia, pauza na północ i zamknięcie przed weekendem.
- Nie otwiera nic nowego, gdy spread jest za szeroki albo trwa pauza rolloveru.

## W jednym zdaniu

Kupno i sprzedaż pracują obok siebie. Każda strona uśrednia swoje straty do wspólnego zera, a gdy koszyk lekko wyjdzie nad kreskę — zamyka się w całości i zaczyna od nowa od małej pozycji.
