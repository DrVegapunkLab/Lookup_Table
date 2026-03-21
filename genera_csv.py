import pandas as pd
import numpy as np

def genera_csv_test(nome_file="dati_test.csv"):
    print(f"Generazione del file {nome_file} in corso...")
    
    # 1. Generiamo l'asse X (es. Temperatura da -20 a 120 °C)
    # Creiamo 30 punti uniformemente distanziati
    temperature = np.linspace(-20, 120, 30)
    
    # 2. Generiamo l'asse Y con una relazione non lineare (es. Tensione in Volt)
    # Simuliamo un comportamento asintotico classico di alcuni sensori
    tensione = 5.0 * (1.0 - np.exp(-(temperature + 20) / 40.0))
    
    # 3. Arrotondiamo i valori per avere un CSV pulito (stile C)
    temperature = np.round(temperature, 1)
    tensione = np.round(tensione, 3)
    
    # 4. Creiamo un DataFrame Pandas
    df = pd.DataFrame({
        'Temperatura_C': temperature,
        'Tensione_V': tensione
    })
    
    # 5. Salviamo su file CSV (senza esportare l'indice di riga)
    df.to_csv(nome_file, index=False)
    
    print(f"Fatto! Il file '{nome_file}' è pronto per essere caricato nella GUI.")

if __name__ == '__main__':
    # Se non hai numpy installato, puoi farlo con: pip install numpy
    genera_csv_test()