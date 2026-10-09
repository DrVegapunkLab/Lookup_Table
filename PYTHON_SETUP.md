# Ambiente Python / virtual environment

Il progetto usa una virtual environment locale chiamata `.venv`.
CMake cerca automaticamente l'interprete in:

- `.venv/bin/python` su Linux/macOS;
- `.venv/Scripts/python.exe` su Windows.

## Requisiti di sistema

- Python **3.10 o successivo**, consigliato a 64 bit;
- `pip` disponibile (`python -m pip --version`);
- CMake e un compilatore C per compilare/eseguire la suite CTest.

Le dipendenze Python del progetto sono dichiarate in `requirements.txt`:

- NumPy: calcolo numerico, quantizzazione e generazione LUT;
- pandas: import/export CSV;
- Matplotlib: grafici della GUI;
- SciPy: ottimizzazione utilizzata dalla GUI;
- PyQt5: interfaccia grafica.

## Creazione manuale della `.venv`

### Windows - PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Se PowerShell impedisce l'attivazione dello script, per la sola sessione corrente:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Windows - Prompt dei comandi (cmd.exe)

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux / macOS

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Su alcune distribuzioni Linux puo' essere necessario installare prima il modulo
`venv` del sistema, ad esempio `python3-venv` tramite il package manager della
distribuzione.

## Creazione automatica

### Linux / macOS

```sh
./setup_venv.sh
```

Se il file non e' eseguibile:

```sh
sh setup_venv.sh
```

### Windows - PowerShell

```powershell
.\setup_venv.ps1
```

Gli script:

1. creano `.venv` se non esiste;
2. aggiornano `pip`;
3. installano `requirements.txt`;
4. verificano gli import principali.

## Verifica dell'ambiente

Con la virtual environment attiva:

```sh
python -c "import numpy, pandas, matplotlib, scipy, PyQt5; print('Python environment OK')"
```

Per avviare la GUI:

```sh
python lut_generator_pyqt.py
```

## Build e test

Non e' obbligatorio attivare la `.venv` prima di eseguire CMake: se la cartella
`.venv` e' nella root del progetto, `CMakeLists.txt` seleziona automaticamente
il relativo interprete Python.

```sh
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

Per verificare quale interprete Python e' stato trovato da CMake, nella fase di
configure viene mostrato il percorso di `Python3_EXECUTABLE` da CMake.

## Aggiornamento delle dipendenze

Per reinstallare/aggiornare rispettando i vincoli del progetto:

```sh
python -m pip install --upgrade -r requirements.txt
```

La cartella `.venv/` e' gia' esclusa dal repository tramite `.gitignore`.
