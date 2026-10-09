#!/usr/bin/env python3
import argparse
from pathlib import Path

import numpy as np

from lut_codegen import C_TYPE_ORDER, generate_c_lut


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    x = np.array([0.0, 2.0, 4.0, 6.0])
    y = np.array([0.0, 10.0, 20.0, 30.0])

    chunks = ["/* AUTO-GENERATO: smoke test combinazioni tipi GUI -> C */\n\n"]
    for bp_type in C_TYPE_ORDER:
        for table_type in C_TYPE_ORDER:
            base = f"smoke_{bp_type}_{table_type}"
            chunks.append(generate_c_lut(base, x, y, bp_type, table_type))
            chunks.append("\n\n")
            chunks.append(generate_c_lut(base + "_pow2", x, y, bp_type, table_type, True, 1))
            chunks.append("\n\n")

    Path(args.output).write_text("".join(chunks), encoding="utf-8")


if __name__ == "__main__":
    main()
