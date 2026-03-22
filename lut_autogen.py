import numpy as np
import os
import concurrent.futures

OUTPUT_HEADER = "test_luts_data.h"

def get_pow2_spacing(x_orig, y_orig, tolerance):
    x_min, x_max = x_orig[0], x_orig[-1]
    for N in range(5, -20, -1):
        dx = 2.0 ** N
        num_intervals = int(np.ceil((x_max - x_min) / dx))
        opt_x = x_min + np.arange(num_intervals + 1) * dx
        opt_y = np.interp(opt_x, x_orig, y_orig)
        y_test = np.interp(x_orig, opt_x, opt_y)
        max_err = np.max(np.abs(y_orig - y_test))
        if max_err <= tolerance:
            return N, opt_x, opt_y
    return 0, x_orig, y_orig

def get_greedy_spacing(x_orig, y_orig, tolerance):
    keep_mask = np.ones(len(x_orig), dtype=bool)
    while True:
        idx_kept = np.where(keep_mask)[0]
        if len(idx_kept) <= 2: break
        min_err = float('inf')
        best_idx = -1
        for i in range(1, len(idx_kept) - 1):
            test_mask = keep_mask.copy()
            test_mask[idx_kept[i]] = False
            y_interp = np.interp(x_orig, x_orig[test_mask], y_orig[test_mask])
            max_err = np.max(np.abs(y_orig - y_interp))
            if max_err < min_err:
                min_err = max_err
                best_idx = idx_kept[i]
        if min_err <= tolerance:
            keep_mask[best_idx] = False
        else:
            break
    return x_orig[keep_mask], y_orig[keep_mask]

# Funzioni di appoggio (il Multiprocessing non accetta funzioni "lambda")
def my_atan2(x): return np.arctan2(x, 1.0)
def my_pow(x):   return np.power(x, 2.5)

# Funzione lavoratrice (eseguita in parallelo da ogni core della CPU)
def process_function(args):
    name, cfg = args
    x_raw = np.linspace(cfg['min'], cfg['max'], 1000)
    y_raw = cfg['func'](x_raw)
    
    out = []
    out.append(f"// ==================== {name.upper()} ====================\n")
    
    # 1. RAW
    out.append(f"const int {name}_raw_num = 1000;\n")
    out.append(f"const double {name}_raw_bp[] = {{ " + ", ".join([f"{v:.6f}" for v in x_raw]) + " };\n")
    out.append(f"const double {name}_raw_table[] = {{ " + ", ".join([f"{v:.6f}" for v in y_raw]) + " };\n\n")

    # 2. GREEDY
    opt_x, opt_y = get_greedy_spacing(x_raw, y_raw, cfg['tol'])
    out.append(f"const int {name}_greedy_num = {len(opt_x)};\n")
    out.append(f"const double {name}_greedy_bp[] = {{ " + ", ".join([f"{v:.6f}" for v in opt_x]) + " };\n")
    out.append(f"const double {name}_greedy_table[] = {{ " + ", ".join([f"{v:.6f}" for v in opt_y]) + " };\n\n")

    # 3. POW2
    N, p2_x, p2_y = get_pow2_spacing(x_raw, y_raw, cfg['tol'])
    out.append(f"const int {name}_pow2_num = {len(p2_y)};\n")
    out.append(f"const double {name}_pow2_min = {p2_x[0]:.6f};\n")
    out.append(f"const double {name}_pow2_spacing = {2.0**N:.6f};\n")
    out.append(f"const double {name}_pow2_inv = {1.0/(2.0**N):.6f};\n")
    out.append(f"const double {name}_pow2_table[] = {{ " + ", ".join([f"{v:.6f}" for v in p2_y]) + " };\n\n")
    
    print(f"  -> [{name.upper()}] Ottimizzazione calcolata.")
    return "".join(out)

def main():
    FUNCTIONS = {
        'acos':  {'func': np.arccos, 'min': -1.0, 'max': 1.0, 'tol': 0.02},
        'asin':  {'func': np.arcsin, 'min': -1.0, 'max': 1.0, 'tol': 0.02},
        'atan':  {'func': np.arctan, 'min': -5.0, 'max': 5.0, 'tol': 0.02},
        'atan2': {'func': my_atan2,  'min': -5.0, 'max': 5.0, 'tol': 0.02},
        'cos':   {'func': np.cos,    'min': 0.0,  'max': 6.28, 'tol': 0.02},
        'cosh':  {'func': np.cosh,   'min': -3.0, 'max': 3.0, 'tol': 0.05},
        'exp':   {'func': np.exp,    'min': 0.0,  'max': 5.0,  'tol': 0.5},
        'log':   {'func': np.log,    'min': 0.1,  'max': 10.0, 'tol': 0.05},
        'log10': {'func': np.log10,  'min': 0.1,  'max': 10.0, 'tol': 0.05},
        'pow':   {'func': my_pow,    'min': 0.0,  'max': 10.0, 'tol': 0.5},
        'sin':   {'func': np.sin,    'min': 0.0,  'max': 6.28, 'tol': 0.02},
        'sinh':  {'func': np.sinh,   'min': -3.0, 'max': 3.0,  'tol': 0.05},
        'sqrt':  {'func': np.sqrt,   'min': 0.0,  'max': 100.0,'tol': 0.1},
        'tan':   {'func': np.tan,    'min': -1.4, 'max': 1.4,  'tol': 0.1},
        'tanh':  {'func': np.tanh,   'min': -3.0, 'max': 3.0,  'tol': 0.02}
    }

    print(f"Generazione delle LUT in PARALLELO ({os.cpu_count()} core rilevati)...")
    
    with open(OUTPUT_HEADER, "w") as f:
        f.write("// AUTO-GENERATO da lut_autogen.py (via Multiprocessing)\n")
        f.write("#ifndef TEST_LUTS_DATA_H\n#define TEST_LUTS_DATA_H\n\n")

        # Assegna il calcolo di ogni funzione a un Core diverso
        with concurrent.futures.ProcessPoolExecutor() as executor:
            # Map esegue process_function per ogni elemento in FUNCTIONS
            results = executor.map(process_function, FUNCTIONS.items())
            
            # Scrive i risultati sul file man mano che i core finiscono
            for res_string in results:
                f.write(res_string)

        f.write("#endif // TEST_LUTS_DATA_H\n")
    print("Generazione completata con successo.")

if __name__ == "__main__":
    main() 