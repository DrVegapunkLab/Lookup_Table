import unittest

import numpy as np

from lut_codegen import (
    C_TYPE_ORDER,
    C_TYPE_SPECS,
    estimate_lut_bytes,
    generate_c_lut,
    prepare_deployed_lut_data,
)


class CodegenTypeTests(unittest.TestCase):
    def setUp(self):
        self.x = np.array([0.0, 2.0, 4.0, 6.0])
        self.y = np.array([0.0, 10.0, 20.0, 30.0])

    def test_standard_codegen_one_type_at_a_time(self):
        for type_key in C_TYPE_ORDER:
            with self.subTest(type_key=type_key):
                spec = C_TYPE_SPECS[type_key]
                code = generate_c_lut(
                    base_name=f"lut_{type_key}",
                    breakpoints=self.x,
                    table=self.y,
                    breakpoint_type=type_key,
                    table_type=type_key,
                )
                self.assertIn(f"static const {spec.c_type} lut_{type_key}_breakpoints[]", code)
                self.assertIn(f"static const {spec.c_type} lut_{type_key}_table[]", code)
                self.assertIn(spec.lut_enum, code)
                self.assertIn("_eval_checked", code)

    def test_pow2_codegen_one_type_at_a_time(self):
        for type_key in C_TYPE_ORDER:
            with self.subTest(type_key=type_key):
                code = generate_c_lut(
                    base_name=f"lut_pow2_{type_key}",
                    breakpoints=self.x,
                    table=self.y,
                    breakpoint_type=type_key,
                    table_type=type_key,
                    is_pow2=True,
                    pow2_n=1,
                )
                self.assertIn("prelookup_pow2_typed", code)
                self.assertIn("x_spacing", code)

    def test_all_input_table_type_combinations_prepare(self):
        for bp_type in C_TYPE_ORDER:
            for table_type in C_TYPE_ORDER:
                with self.subTest(bp_type=bp_type, table_type=table_type):
                    xq, yq = prepare_deployed_lut_data(
                        self.x, self.y, bp_type, table_type, False, 0
                    )
                    self.assertEqual(len(xq), 4)
                    self.assertEqual(len(yq), 4)
                    self.assertTrue(np.all(np.diff(xq) > 0))

    def test_standard_codegen_all_mixed_input_output_types(self):
        for input_type in C_TYPE_ORDER:
            for output_type in C_TYPE_ORDER:
                if input_type == output_type:
                    continue
                with self.subTest(input_type=input_type, output_type=output_type):
                    input_spec = C_TYPE_SPECS[input_type]
                    output_spec = C_TYPE_SPECS[output_type]
                    code = generate_c_lut(
                        base_name=f"mixed_{input_type}_to_{output_type}",
                        breakpoints=self.x,
                        table=self.y,
                        breakpoint_type=input_type,
                        table_type=output_type,
                    )
                    self.assertIn(
                        f"static const {input_spec.c_type} mixed_{input_type}_to_{output_type}_breakpoints[]",
                        code,
                    )
                    self.assertIn(
                        f"static const {output_spec.c_type} mixed_{input_type}_to_{output_type}_table[]",
                        code,
                    )
                    self.assertIn(input_spec.lut_enum, code)
                    self.assertIn(output_spec.lut_enum, code)
                    self.assertIn(
                        f"LutStatus mixed_{input_type}_to_{output_type}_eval_checked({input_spec.c_type} input, double *output)",
                        code,
                    )

    def test_pow2_codegen_all_mixed_input_output_types(self):
        for input_type in C_TYPE_ORDER:
            for output_type in C_TYPE_ORDER:
                if input_type == output_type:
                    continue
                with self.subTest(input_type=input_type, output_type=output_type):
                    input_spec = C_TYPE_SPECS[input_type]
                    output_spec = C_TYPE_SPECS[output_type]
                    code = generate_c_lut(
                        base_name=f"mixed_pow2_{input_type}_to_{output_type}",
                        breakpoints=self.x,
                        table=self.y,
                        breakpoint_type=input_type,
                        table_type=output_type,
                        is_pow2=True,
                        pow2_n=1,
                    )
                    self.assertIn(
                        f"static const {input_spec.c_type} mixed_pow2_{input_type}_to_{output_type}_x_min",
                        code,
                    )
                    self.assertIn(
                        f"static const {output_spec.c_type} mixed_pow2_{input_type}_to_{output_type}_table[]",
                        code,
                    )
                    self.assertIn("prelookup_pow2_typed", code)
                    self.assertIn(output_spec.lut_enum, code)

    def test_unsigned_rejects_negative_data(self):
        with self.assertRaisesRegex(ValueError, "fuori range"):
            generate_c_lut("bad", [-1, 0, 1], [0, 1, 2], "uint8", "uint8")

    def test_integer_overflow_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "fuori range"):
            generate_c_lut("bad", [0, 1, 2], [0, 128, 200], "int8", "int8")

    def test_breakpoint_collapse_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "breakpoint uguali/non crescenti"):
            generate_c_lut("bad", [0.0, 0.25, 0.5], [0, 1, 2], "int16", "int16")

    def test_float32_precision_collapse_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "breakpoint uguali/non crescenti"):
            generate_c_lut("bad", [1e8, 1e8 + 1, 1e8 + 2], [0, 1, 2], "float32", "float32")

    def test_fractional_pow2_spacing_rejected_for_integer_breakpoint_type(self):
        x = [0.0, 0.5, 1.0, 1.5]
        with self.assertRaisesRegex(ValueError, "spaziatura"):
            generate_c_lut(
                "bad_pow2", x, [0, 1, 2, 3], "int16", "int16", True, -1
            )

    def test_memory_estimate_uses_selected_storage_width(self):
        self.assertEqual(estimate_lut_bytes(10, "uint8", "uint8", False), 20)
        self.assertEqual(estimate_lut_bytes(10, "float64", "float64", False), 160)
        self.assertLess(
            estimate_lut_bytes(10, "uint8", "uint8", True),
            estimate_lut_bytes(10, "uint8", "uint8", False) + 32,
        )


if __name__ == "__main__":
    unittest.main()
