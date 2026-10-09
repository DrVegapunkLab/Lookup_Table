# Test coverage dei tipi C

La suite mantiene i 49 test matematici originali sull'API `double` e verifica
l'API typed su tutti i 10 tipi supportati:

- `float` / `float32`
- `double` / `float64`
- `int8_t`, `uint8_t`
- `int16_t`, `uint16_t`
- `int32_t`, `uint32_t`
- `int64_t`, `uint64_t`

## 49 scenari per coppia input/output

Ogni configurazione esegue gli stessi 49 scenari:

- 15 funzioni matematiche x `raw`, `greedy`, `pow2` = 45 test 1D;
- LUT 2D planare `raw` e `pow2` = 2 test;
- LUT 2D non lineare `raw` e `pow2` = 2 test.

Oltre ai 10 casi omogenei (`input == output`), vengono testate tutte le 90
coppie eterogenee (`input != output`). In totale l'API typed viene quindi
provata su **100 coppie input/output x 49 scenari = 4900 test runtime C**.

Esempi di coppie ora coperte:

- `float32 -> int8`
- `uint8 -> float64`
- `int16 -> uint32`
- `uint64 -> float32`
- e tutte le altre combinazioni ordinate tra i 10 tipi.

Per le LUT 2D il tipo input e' usato per entrambi gli assi dei breakpoint,
mentre il tipo output e' il tipo della tabella, coerentemente con il modello
attuale del generatore GUI.

Sono inoltre mantenuti 10 test dedicati agli error path, uno per ogni tipo.

## Totale CTest

- 49 test legacy `double`;
- 490 test typed omogenei (49 x 10 tipi);
- 4410 test typed mixed (49 x 90 coppie diverse);
- 10 test typed error-path;
- 1 test Python di code generation/quantizzazione;
- **4960 test CTest totali**.

Il test Python e la fixture compilata continuano inoltre a verificare la
preparazione/generazione C di tutte le 10 x 10 combinazioni di tipi.

## Perche' i dataset typed non copiano byte-per-byte quelli legacy

Le LUT legacy contengono molti breakpoint frazionari. Convertirli direttamente
in un tipo intero causerebbe breakpoint duplicati (per esempio tanti valori tra
`-1` e `1` diventerebbero `0`) e quindi una LUT correttamente rifiutata come non
monotona.

I test typed mantengono gli stessi scenari/funzioni, ma costruiscono una griglia
rappresentabile nel tipo input. I valori della funzione vengono quantizzati
separatamente nel tipo output. Il risultato dell'API viene confrontato con un
oracolo indipendente che interpola i valori *effettivamente memorizzati* nei due
tipi. Questo verifica davvero la separazione tra tipo dei breakpoint e tipo
della tabella.

## Esecuzione

```sh
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

Per eseguire i 49 test di un tipo omogeneo:

```sh
ctest --test-dir build -R 'TestTyped49_int8_'
```

Per eseguire una singola coppia mixed:

```sh
ctest --test-dir build -R 'TestTypedMixed49_int16_to_float32_'
```

Per eseguire tutti i test input/output differenti:

```sh
ctest --test-dir build -L typed_mixed
```

## Ambiente Python

Prima della build e dei test e' consigliato creare la virtual environment locale
`.venv`, installando tutte le dipendenze dichiarate in `requirements.txt`.
Le istruzioni complete per Windows, Linux e macOS sono in `PYTHON_SETUP.md`.

Setup rapido Linux/macOS:

```sh
./setup_venv.sh
```

Setup rapido Windows PowerShell:

```powershell
.\setup_venv.ps1
```

Il `CMakeLists.txt` usa automaticamente il Python contenuto in `.venv` quando
la cartella e' presente nella root del progetto.
