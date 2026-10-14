# Jak działa bot — wersja 2.2.0 (aktualna)

Ta wersja łączy dwie rzeczy, które wcześniej były rozdzielone:

- gdy masz **tylko jedną** pozycję — bot poluje na normalny, sztywny Take Profit (jak zwykłe zlecenie);
- gdy musi **uśredniać** (dokłada drugą i kolejne nogi) — przechodzi na wspólny koszyk i wychodzi trochę nad zerem.

Kupno i sprzedaż nadal pracują **osobno**. Jedna strona nie blokuje drugiej.

## Tryb 1: pojedyncza baza

Na starcie bot otwiera małe kupno i małą sprzedaż.

Każda z tych pozycji dostaje sztywny Take Profit w punktach — domyślnie **200 punktów** (`BaseTakeProfitPoints`).  
Na XAUUSD z 2 miejscami po przecinku to zwykle **2.00 USD** ruchu ceny.

- Cena idzie w Twoją stronę → broker zamyka pozycję na TP.
- Bot od razu stawia **nową, małą bazę** tej samej strony, znowu z TP 200 pkt.

Na wykresie widać linię tego TP. MT5 też pokazuje standardową kreskę Take Profit zlecenia.

W tym trybie bot **nie** zamyka pozycji za 0.50 USD. Mały cel dolarowy czeka na koszyk.

## Tryb 2: uśrednianie (dwie lub więcej pozycji)

Jeśli cena idzie przeciwko bazie o jeden krok siatki, bot dokłada większą pozycję w tym samym kierunku.

Od tej chwili:

- nowa noga **nie ma** własnego TP ani Stop Loss;
- z pierwszej pozycji **zdejmowany** jest stary TP 200 pkt;
- cały zestaw staje się jednym koszykiem.

Bot liczy średnią cenę wejścia (większa noga ciągnie średnią mocniej). To jest **punkt zero** koszyka — niebieska lub czerwona ciągła linia.

Zamyka wszystko razem, gdy łącznie uzbiera mały zysk w walucie konta — domyślnie **0.50 USD** (`BasketProfitTarget_USD`). Przerywana linia pokazuje ten cel na wykresie.

Po zamknięciu koszyka wraca tryb 1: nowa pojedyncza baza ze sztywnym TP 200 pkt.

## W jednym zdaniu

Dopóki jest jedna noga — zwykły Take Profit. Gdy trzeba dokładać — wspólne zero i mały zysk na pokrycie kosztów, potem znowu czysta baza.
