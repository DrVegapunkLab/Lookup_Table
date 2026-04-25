import pandas as pd
import numpy as np

def genera_dataset_esempio(filename="log_acquisizione.csv", n_punti=2000):
    print(f"Generazione di {n_punti} punti in corso...")
    
    # 1. Generiamo il vettore tempo (es. 20 secondi a 100Hz)
    tempo = np.linspace(0, 20, n_punti)
    
    # 2. Generiamo un segnale di input X che varia nel tempo
    # Simula un pedale o un potenziometro che sale e scende
    input_x = 50 + 45 * np.sin(0.5 * tempo) + np.random.normal(0, 0.2, n_punti)
    input_x = np.clip(input_x, 0, 100) # Limita tra 0 e 100
    
    # 3. Definiamo la funzione fisica reale (Plant)
    # Esempio: Y = sqrt(X) * 10 + offset
    def funzione_reale(x):
        return np.sqrt(x) * 10 + 5
    
    # 4. Generiamo l'output Y misurato con rumore di fondo
    output_y_puro = funzione_reale(input_x)
    rumore = np.random.normal(0, 0.8, n_punti) # Rumore del sensore
    output_y_misurato = output_y_puro + rumore
    
    # 5. Creiamo il DataFrame
    df = pd.DataFrame({
        'timestamp_s': tempo,
        'sensore_input_V': input_x,
        'sensore_output_bar': output_y_misurato
    })
    
    # 6. Salvataggio
    df.to_csv(filename, index=False)
    print(f"File '{filename}' creato con successo!")
    print("Colonne disponibili: 'timestamp_s', 'sensore_input_V', 'sensore_output_bar'")

if __name__ == "__main__":
    genera_dataset_esempio()