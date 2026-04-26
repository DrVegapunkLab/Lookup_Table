import argparse
import numpy as np
import pandas as pd


def genera_csv_1d(nome_file="dati_test_1d.csv"):
    temperature = np.linspace(-20, 120, 30)
    tensione = 5.0 * (1.0 - np.exp(-(temperature + 20) / 40.0))

    df = pd.DataFrame({
        "Temperatura_C": np.round(temperature, 1),
        "Tensione_V": np.round(tensione, 3),
    })

    df.to_csv(nome_file, index=False)
    print(f"Creato CSV 1D: {nome_file}")


def genera_csv_2d(nome_file="dati_test_2d.csv"):
    temperatura = np.linspace(-20, 120, 30)
    pressione = np.linspace(0.8, 1.2, 16)

    tt, pp = np.meshgrid(temperatura, pressione, indexing="ij")

    # Esempio superficie sensore: non lineare ma regolare.
    tensione = (
        5.0 * (1.0 - np.exp(-(tt + 20) / 40.0))
        + 0.7 * (pp - 1.0)
        + 0.05 * np.sin(tt / 15.0)
    )

    df = pd.DataFrame({
        "Temperatura_C": np.round(tt.ravel(), 3),
        "Pressione_bar": np.round(pp.ravel(), 5),
        "Tensione_V": np.round(tensione.ravel(), 6),
    })

    df.to_csv(nome_file, index=False)
    print(f"Creato CSV 2D: {nome_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["1d", "2d", "both"], default="both")
    parser.add_argument("--out1d", default="dati_test_1d.csv")
    parser.add_argument("--out2d", default="dati_test_2d.csv")
    args = parser.parse_args()

    if args.mode in ("1d", "both"):
        genera_csv_1d(args.out1d)

    if args.mode in ("2d", "both"):
        genera_csv_2d(args.out2d)


if __name__ == "__main__":
    main()
