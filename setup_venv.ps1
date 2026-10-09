$ErrorActionPreference = "Stop"

function Resolve-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @("py", "-3")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }
    throw "Python 3 non trovato. Installa Python 3.10 o successivo."
}

$PythonCommand = Resolve-PythonCommand
$PythonExe = $PythonCommand[0]
$PythonArgs = @()
if ($PythonCommand.Length -gt 1) {
    $PythonArgs = $PythonCommand[1..($PythonCommand.Length - 1)]
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creazione .venv..."
    & $PythonExe @PythonArgs -m venv .venv
} else {
    Write-Host ".venv gia' presente: riutilizzo ambiente esistente."
}

$VenvPython = Join-Path ".venv" "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Interprete della virtual environment non trovato: $VenvPython"
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt
& $VenvPython -c "import numpy, pandas, matplotlib, scipy, PyQt5; print('Python environment OK')"

Write-Host "Ambiente pronto. Attivazione: .\.venv\Scripts\Activate.ps1"
