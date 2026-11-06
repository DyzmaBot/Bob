# DYZMA — Discord dla NikodemDyzmaYT

**Wersja 1.0** • Czarny + czerwony • Prosty serwer streamera z jednym własnym botem.

Ten projekt jest **oddzielny od KlanikYT**. Niczego nie kopiuje z jego bazy, a bot nie zadziała na innym Discordzie niż wybrany w `GUILD_ID`.

## Co zrobi bot?

Po komendzie `/dyzma_setup` utworzy brakujące kanały, role i podstawowe panele. Nie robi tego samodzielnie przy każdym uruchomieniu, więc nie zaskoczy właściciela.

### Plan serwera

```text
💬 SPOŁECZNOŚĆ             (od góry po akceptacji)
  # chat
  # szukam-ekipy
  # propozycje-gier
  # klipy-i-screeny
📌 INFORMACJE
  # ogloszenia
  # na-zywo
  # plan-streamow
  # powitania
🎧 GŁOSOWE
  🔊 pogaduchy
  🔊 wspolne-granie (do 5 osób)
🔒 EKIPA                   (widzą tylko moderatorzy i administrator)
  # moderacja
  # panel-administracji
✅ START                   (dostępny przed akceptacją)
  # regulamin
```

**Nie ma** sztucznego XP, wirtualnych pieniędzy, 100 rang, konkursów ani ciężkiego systemu bota. Są wyłącznie rzeczy przydatne na początku.

### Role

- `Widz` — nadawana po kliknięciu **Akceptuję regulamin**. Otwiera resztę serwera.
- `Moderator` — nadaje **właściciel ręcznie**, z poziomu Discorda. Daje dostęp do panelu ekipy. Bot sam nikogo nie awansuje na moderatora.
- Właściciel serwera ma dostęp zawsze.

### Prywatny panel — bez komend

Panel w `#panel-administracji` ma przyciski:

1. **📅 Zmień plan** — wpisz godziny w formularzu. Widoczna tabela planu aktualizuje się w `#plan-streamow`.
2. **📣 Ogłoszenie** — wpisz tytuł i treść; bot publikuje je w `#ogloszenia`.
3. **🔴 Jestem na żywo** — wpisz tytuł i opcjonalnie link do konkretnej transmisji (domyślnie link `/live` kanału YouTube); bot publikuje powiadomienie w `#na-zywo`.
4. **👋 Edytuj powitanie** — zmień treść widoczną w `#powitania`.

Uczestnicy widzą tylko **publiczne wiadomości**, bez panelu administracji. Przyciski są trwałe i działają po restarcie bota.

## Instalacja na GitHubie / hostingu Python

1. Utwórz puste repozytorium dla **NikodemDyzmaYT**, **nie** wrzucaj plików do repozytorium KlanikYT.
2. Skopiuj wszystkie pliki z paczki do głównego katalogu nowego repozytorium.
3. Skopiuj `.env.example` do `.env`. Wpisz `DISCORD_TOKEN` i `GUILD_ID`. Nie publikuj `.env` ani tokena na GitHubie!
4. Jeżeli używasz Bisection lub innego hostingu, który aktualizuje pliki z GitHuba, dodaj `DISCORD_TOKEN` i `GUILD_ID` **w prywatnych zmiennych środowiskowych hostingu**. Nie w repozytorium.
5. Zainstaluj zależności: `pip install -r requirements.txt`.
6. Uruchom proces: `python bot.py`.
7. Na Discordzie jako właściciel/admin użyj `/dyzma_setup`, a następnie kliknij **Tak, utwórz serwer DYZMA**.
8. Przed zaproszeniem ludzi sprawdź dostęp przez konto bez rangi `Widz`; tylko `#regulamin` powinien być dostępny. Po kliknięciu przycisku pozostałe kanały mają być widoczne, a `#chat` na górze.
9. Przyznaj zaufanym moderatorom rolę `Moderator` ręcznie.

**Uwaga:** w sytuacji, gdy bot został już dodany do Discorda, może być konieczne ponowne zaproszenie ze scope `bot` i `applications.commands` oraz właściwymi uprawnieniami. Musi mieć m.in. `Zarządzanie kanałami`, `Zarządzanie rolami`, `Wyświetlanie kanałów`, `Wysyłanie wiadomości`, `Osadzanie linków`, `Czytanie historii wiadomości` i `Przypinanie wiadomości` (Manage Messages). Nie dawaj mu `Administrator`, jeśli nie trzeba.

Rola **bota** musi znajdować się **nad rolą Widz** w ustawieniach ról Discorda. Jeśli rola bota jest niżej, przycisk akceptacji nie przydzieli dostępu.

### Skąd wziąć wartości?

- `DISCORD_TOKEN`: https://discord.com/developers/applications -> wybrany bot -> Bot -> Token (prywatne). Jeśli znajomy dodał już jakiegoś gotowego bota z katalogu, **nie da się uruchomić na nim tego kodu** — potrzebna jest własna aplikacja bot w Discord Developer Portal.
- `GUILD_ID`: Włącz Tryb dewelopera w ustawieniach Discorda, kliknij prawym przyciskiem serwer i wybierz Kopiuj ID.

### Ważne o istniejącym botcie znajomego

Jeśli to **jego własny bot**, może wykorzystać ten kod, pod warunkiem że ma do niego token i kontroluje hosting. Jeśli to **cudzy bot**, np. Dyno, MEE6, Carl-bot, nie wolno i nie da się zastąpić jego kodu tą paczką; wtedy potrzebny jest drugi, własny DyzmaBot.

## Automatyczne ogłoszenia YouTube LIVE (opcjonalne)

Ręczny przycisk **🔴 Jestem na żywo** działa bez jakiegokolwiek API.

Jeśli chcecie automatyczne wykrywanie streamów:

1. W Google Cloud włącz YouTube Data API v3 i stwórz klucz API.
2. W `.env` lub prywatnych zmiennych hostingu ustaw `YOUTUBE_API_KEY` oraz `YOUTUBE_CHANNEL_ID` (kanoniczny identyfikator kanału zaczynający się od `UC`, **nie** `@NikodemDyzmaYT`).
3. Bot sprawdza YouTube co 20 minut i ogłasza **jedną transmisję tylko raz**. Opóźnienie do 20 minut i dodatkowa zwłoka indeksowania YouTube są możliwe.
4. Te ustawienia są opcjonalne: bez nich nadal działają wszystkie inne funkcje.

Google stosuje limity API — nie należy zmniejszać interwału bez sprawdzenia limitu konta.

## Zapisywanie i bezpieczeństwo

- `data/state.json` zawiera plan, treść powitania, identyfikatory stałych wiadomości i ID ostatniego ogłoszonego live. Zapis jest atomowy (plik tymczasowy + zamiana).
- Folder `data/` jest w `.gitignore` — **hostowanie z GitHub auto-update nie może go kasować przy wdrożeniu**. Jeżeli hosting robi czystą podmianę katalogu, trzeba skonfigurować trwały dysk/katalog.
- Nie ma mechanizmu resetu i kasowania cudzych kanałów. Ponowna instalacja odświeża istniejące panele i uprawnienia kategorii o identycznych nazwach; nie powinna tworzyć kolejnych kopii takich samych kanałów wewnątrz tej samej kategorii.
- Zablokowaliśmy masowe wzmianki przez bota (`@everyone`, `@here` itd.).
- Zwykły użytkownik nie ma dostępu do przycisków panelu moderacji; dostęp jest sprawdzany przy każdej interakcji.

## Rzeczy, których bot **nie** robi

- Nie loguje się na YouTube i nie czyta prywatnych wiadomości ani transmisji bez opcjonalnego API.
- Nie pobiera grafik/banera ani nie ustawia nazwy i zdjęcia serwera, ponieważ wymaga to uprawnień i decyzji właściciela.
- Nie przenosi automatycznie ekranu użytkownika na `#chat`: Discord nie udostępnia takiego sterowania; przycisk akceptacji podaje bezpośredni link.
- Nie hostuje się sam — musi działać na komputerze lub hostingu 24/7.

## Testowanie

`python -m unittest discover -s tests -v`

Testy obejmują zapis ustawień bez Discorda. Działanie rzeczywistych kanałów, przycisków i uprawnień trzeba zweryfikować po uruchomieniu bota na Discordzie.
