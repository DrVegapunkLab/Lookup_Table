#!/usr/bin/env python3
import argparse
import concurrent.futures
import os
import numpy as np


def rdp_simplify(x, y, tol):
    keep = np.zeros(len(x), dtype=bool)
    keep[0] = True
    keep[-1] = True
    stack = [(0, len(x) - 1)]

    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue

        yi = np.interp(x[start:end + 1], [x[start], x[end]], [y[start], y[end]])
        err = np.abs(y[start:end + 1] - yi)
        idx_rel = int(np.argmax(err))
        max_err = float(err[idx_rel])

        if max_err > tol:
            idx_abs = start + idx_rel
            keep[idx_abs] = True
            stack.append((start, idx_abs))
            stack.append((idx_abs, end))

    return x[keep], y[keep]


def get_pow2_spacing(x_orig, y_orig, tolerance):
    x_min, x_max = float(x_orig[0]), float(x_orig[-1])

    for n in range(10, -25, -1):
        dx = 2.0 ** n
        num_intervals = int(np.ceil((x_max - x_min) / dx))

        if num_intervals < 1 or num_intervals > 2_000_000:
            continue

        opt_x = x_min + np.arange(num_intervals + 1, dtype=float) * dx

        # Mantiene griglia uniforme: non appendere x_max non allineato.
        if opt_x[-1] < x_max:
            opt_x = x_min + np.arange(num_intervals + 2, dtype=float) * dx

        opt_y = np.interp(opt_x, x_orig, y_orig)
        y_test = np.interp(x_orig, opt_x, opt_y)
        max_err = float(np.max(np.abs(y_orig - y_test)))

        if max_err <= tolerance:
            return n, opt_x, opt_y

    return 0, x_orig, y_orig


def c_array(name, values):
    values = np.asarray(values, dtype=float).ravel()
    return f"static const double {name}[] = {{ " + ", ".join(f"{v:.17g}" for v in values) + " };\n"


def c_array_2d_flat(name, table):
    table = np.asarray(table, dtype=float)
    rows = []
    for row in table:
        rows.append(", ".join(f"{v:.17g}" for v in row))
    return f"static const double {name}[] = {{\n    " + ",\n    ".join(rows) + "\n};\n"


def my_atan2(x):
    return np.arctan2(x, 1.0)


def my_pow(x):
    return np.power(x, 2.5)


def process_function(args):
    name, cfg = args
    x_raw = np.linspace(cfg["min"], cfg["max"], 1000)
    y_raw = cfg["func"](x_raw)

    out = []
    out.append(f"/* ==================== {name.upper()} ==================== */\n")

    out.append(f"static const int {name}_raw_num = {len(x_raw)};\n")
    out.append(c_array(f"{name}_raw_bp", x_raw))
    out.append(c_array(f"{name}_raw_table", y_raw))
    out.append("\n")

    opt_x, opt_y = rdp_simplify(x_raw, y_raw, cfg["tol"])
    out.append(f"static const int {name}_greedy_num = {len(opt_x)};\n")
    out.append(c_array(f"{name}_greedy_bp", opt_x))
    out.append(c_array(f"{name}_greedy_table", opt_y))
    out.append("\n")

    n, p2_x, p2_y = get_pow2_spacing(x_raw, y_raw, cfg["tol"])
    out.append(f"static const int {name}_pow2_num = {len(p2_y)};\n")
    out.append(f"static const double {name}_pow2_min = {p2_x[0]:.17g};\n")
    out.append(f"static const double {name}_pow2_spacing = {2.0 ** n:.17g};\n")
    out.append(f"static const double {name}_pow2_inv = {1.0 / (2.0 ** n):.17g};\n")
    out.append(c_array(f"{name}_pow2_table", p2_y))
    out.append("\n")

    print(f"  -> [{name.upper()}] generata")
    return "".join(out)


def generate_2d(out):
    # LUT 2D lineare: z = 2*x + 3*y + 1
    x = np.linspace(-2.0, 2.0, 9)
    y = np.linspace(-1.0, 3.0, 11)
    xx, yy = np.meshgrid(x, y, indexing="ij")
    z = 2.0 * xx + 3.0 * yy + 1.0

    out.write("/* ==================== LUT2D_PLANE ==================== */\n")
    out.write(f"static const int lut2d_plane_raw_rows = {len(x)};\n")
    out.write(f"static const int lut2d_plane_raw_cols = {len(y)};\n")
    out.write(c_array("lut2d_plane_raw_row_bp", x))
    out.write(c_array("lut2d_plane_raw_col_bp", y))
    out.write(c_array_2d_flat("lut2d_plane_raw_table", z))
    out.write("\n")

    # pow2: spacing 0.5 per entrambi.
    out.write(f"static const int lut2d_plane_pow2_rows = {len(x)};\n")
    out.write(f"static const int lut2d_plane_pow2_cols = {len(y)};\n")
    out.write("static const double lut2d_plane_pow2_row_min = -2.0;\n")
    out.write("static const double lut2d_plane_pow2_row_spacing = 0.5;\n")
    out.write("static const double lut2d_plane_pow2_row_inv = 2.0;\n")
    out.write("static const double lut2d_plane_pow2_col_min = -1.0;\n")
    out.write("static const double lut2d_plane_pow2_col_spacing = 0.4;\n")
    out.write("static const double lut2d_plane_pow2_col_inv = 2.5;\n")
    out.write(c_array_2d_flat("lut2d_plane_pow2_table", z))
    out.write("\n")

    # LUT 2D non lineare: z = sin(x) + cos(y)
    x2 = np.linspace(-3.0, 3.0, 41)
    y2 = np.linspace(-2.0, 2.0, 31)
    xx2, yy2 = np.meshgrid(x2, y2, indexing="ij")
    z2 = np.sin(xx2) + np.cos(yy2)

    out.write("/* ==================== LUT2D_NONLINEAR ==================== */\n")
    out.write(f"static const int lut2d_nonlinear_raw_rows = {len(x2)};\n")
    out.write(f"static const int lut2d_nonlinear_raw_cols = {len(y2)};\n")
    out.write(c_array("lut2d_nonlinear_raw_row_bp", x2))
    out.write(c_array("lut2d_nonlinear_raw_col_bp", y2))
    out.write(c_array_2d_flat("lut2d_nonlinear_raw_table", z2))
    out.write("\n")

    # pow2 esteso: 1/8 = 0.125 copre range.
    x2p = -3.0 + np.arange(int(np.ceil((3.0 - (-3.0)) / 0.125)) + 1) * 0.125
    y2p = -2.0 + np.arange(int(np.ceil((2.0 - (-2.0)) / 0.125)) + 1) * 0.125
    xx2p, yy2p = np.meshgrid(x2p, y2p, indexing="ij")
    z2p = np.sin(xx2p) + np.cos(yy2p)

    out.write(f"static const int lut2d_nonlinear_pow2_rows = {len(x2p)};\n")
    out.write(f"static const int lut2d_nonlinear_pow2_cols = {len(y2p)};\n")
    out.write("static const double lut2d_nonlinear_pow2_row_min = -3.0;\n")
    out.write("static const double lut2d_nonlinear_pow2_row_spacing = 0.125;\n")
    out.write("static const double lut2d_nonlinear_pow2_row_inv = 8.0;\n")
    out.write("static const double lut2d_nonlinear_pow2_col_min = -2.0;\n")
    out.write("static const double lut2d_nonlinear_pow2_col_spacing = 0.125;\n")
    out.write("static const double lut2d_nonlinear_pow2_col_inv = 8.0;\n")
    out.write(c_array_2d_flat("lut2d_nonlinear_pow2_table", z2p))
    out.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="test_luts_data.h")
    args = parser.parse_args()

    functions = {
        "acos":  {"func": np.arccos, "min": -1.0, "max": 1.0, "tol": 0.02},
        "asin":  {"func": np.arcsin, "min": -1.0, "max": 1.0, "tol": 0.02},
        "atan":  {"func": np.arctan, "min": -5.0, "max": 5.0, "tol": 0.02},
        "atan2": {"func": my_atan2,  "min": -5.0, "max": 5.0, "tol": 0.02},
        "cos":   {"func": np.cos,    "min": 0.0,  "max": 6.28, "tol": 0.02},
        "cosh":  {"func": np.cosh,   "min": -3.0, "max": 3.0, "tol": 0.05},
        "exp":   {"func": np.exp,    "min": 0.0,  "max": 5.0,  "tol": 0.5},
        "log":   {"func": np.log,    "min": 0.1,  "max": 10.0, "tol": 0.05},
        "log10": {"func": np.log10,  "min": 0.1,  "max": 10.0, "tol": 0.05},
        "pow":   {"func": my_pow,    "min": 0.0,  "max": 10.0, "tol": 0.5},
        "sin":   {"func": np.sin,    "min": 0.0,  "max": 6.28, "tol": 0.02},
        "sinh":  {"func": np.sinh,   "min": -3.0, "max": 3.0,  "tol": 0.05},
        "sqrt":  {"func": np.sqrt,   "min": 0.0,  "max": 100.0, "tol": 0.1},
        "tan":   {"func": np.tan,    "min": -1.4, "max": 1.4,  "tol": 0.1},
        "tanh":  {"func": np.tanh,   "min": -3.0, "max": 3.0,  "tol": 0.02},
    }

    print(f"Generazione LUT 1D/2D ({os.cpu_count()} core rilevati)...")

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("/* AUTO-GENERATO da lut_autogen.py */\n")
        f.write("#ifndef TEST_LUTS_DATA_H\n#define TEST_LUTS_DATA_H\n\n")

        with concurrent.futures.ProcessPoolExecutor() as executor:
            for result in executor.map(process_function, functions.items()):
                f.write(result)

        generate_2d(f)

        f.write("#endif\n")

    print(f"Generazione completata: {args.output}")


if __name__ == "__main__":
    main()
