#include <stdio.h>
#include <math.h>
#include "simulink_lookup.h"

int main() {
    printf("=== Test Libreria Simulink Lookup ===\n\n");

    // =========================================================
    // 1. TEST 1D STANDARD (Binary Search)
    // =========================================================
    printf("1. Test 1D Standard (prelookup)\n");

    const double bp_std[]    = {0.0, 10.0, 50.0, 100.0};
    const double table_std[] = {0.0, 20.0, 80.0, 100.0};
    int num_std = 4;

    double in_std = 30.0;

    PrelookupResult res_std = prelookup(
        in_std,
        bp_std,
        num_std,
        EXTRAP_CLIP
    );

    double out_std = interpolate_1d(res_std, table_std);

    printf("Input: %.2f -> Output: %.2f (k=%d, f=%.3f)\n\n",
           in_std, out_std, res_std.k, res_std.f);


    // =========================================================
    // 2. TEST 1D POW2 (O(1))
    // =========================================================
    printf("2. Test 1D EvenPow2Spacing (O(1))\n");

    const int num_pow2 = 5;
    const double x_min = 0.0;
    const double spacing = 2.0;
    const double inv_spacing = 0.5;

    const double table_pow2[] = {
        0.0, 10.0, 40.0, 90.0, 160.0
    };

    double in_pow2 = 5.0;

    PrelookupResult res_pow2 = prelookup_pow2(
        in_pow2,
        x_min,
        spacing,
        inv_spacing,
        num_pow2,
        EXTRAP_CLIP
    );

    double out_pow2 = interpolate_1d(res_pow2, table_pow2);

    printf("Input: %.2f -> Output: %.2f (k=%d, f=%.3f)\n\n",
           in_pow2, out_pow2, res_pow2.k, res_pow2.f);


    // =========================================================
    // 3. TEST 2D STANDARD (bilineare)
    // =========================================================
    printf("3. Test LUT 2D Standard\n");

    const double bp_row[] = {0.0, 1.0, 2.0};
    const double bp_col[] = {0.0, 5.0, 10.0};

    const int num_rows = 3;
    const int num_cols = 3;

    // z = 2*x + 3*y
    const double table_2d[] = {
        0.0, 15.0, 30.0,
        2.0, 17.0, 32.0,
        4.0, 19.0, 34.0
    };

    double x_in = 1.2;
    double y_in = 6.0;

    PrelookupResult kf_row = prelookup(
        x_in,
        bp_row,
        num_rows,
        EXTRAP_CLIP
    );

    PrelookupResult kf_col = prelookup(
        y_in,
        bp_col,
        num_cols,
        EXTRAP_CLIP
    );

    double out_2d = interpolate_2d(
        kf_row,
        kf_col,
        table_2d,
        num_cols
    );

    printf("Input: (%.2f, %.2f) -> Output: %.3f (k_row=%d, k_col=%d)\n\n",
           x_in, y_in, out_2d, kf_row.k, kf_col.k);


    // =========================================================
    // 4. TEST 2D POW2 (super veloce)
    // =========================================================
    printf("4. Test LUT 2D EvenPow2Spacing (O(1))\n");

    const double row_min = 0.0;
    const double row_spacing = 1.0;
    const double row_inv = 1.0;

    const double col_min = 0.0;
    const double col_spacing = 5.0;
    const double col_inv = 0.2;

    double out_2d_pow2;

    PrelookupResult kf_row2 = prelookup_pow2(
        x_in,
        row_min,
        row_spacing,
        row_inv,
        num_rows,
        EXTRAP_CLIP
    );

    PrelookupResult kf_col2 = prelookup_pow2(
        y_in,
        col_min,
        col_spacing,
        col_inv,
        num_cols,
        EXTRAP_CLIP
    );

    out_2d_pow2 = interpolate_2d(
        kf_row2,
        kf_col2,
        table_2d,
        num_cols
    );

    printf("Input: (%.2f, %.2f) -> Output: %.3f (k_row=%d, k_col=%d)\n\n",
           x_in, y_in, out_2d_pow2, kf_row2.k, kf_col2.k);


    // =========================================================
    // 5. TEST EXTRAPOLAZIONE
    // =========================================================
    printf("5. Test Extrapolation\n");

    double out_clip = interpolate_1d(
        prelookup(-10.0, bp_std, num_std, EXTRAP_CLIP),
        table_std
    );

    double out_linear = interpolate_1d(
        prelookup(-10.0, bp_std, num_std, EXTRAP_LINEAR),
        table_std
    );

    printf("Input fuori range = -10\n");
    printf("Clip: %.3f | Linear: %.3f\n", out_clip, out_linear);

    printf("\n=== Fine Test ===\n");

    return 0;
}