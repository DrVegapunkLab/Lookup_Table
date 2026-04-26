#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>

#include "simulink_lookup.h"
#include "test_luts_data.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define RUN_TEST_STD(MODE, NAME, MATH_EVAL, MIN, MAX, STEP, TOL) \
    do { \
        double max_err = 0.0; \
        double x; \
        for (x = (MIN); x <= (MAX); x += (STEP)) { \
            double real_val = (MATH_EVAL); \
            PrelookupResult kf = prelookup(x, NAME##_##MODE##_bp, NAME##_##MODE##_num, EXTRAP_CLIP); \
            double lut_val = interpolate_1d(kf, NAME##_##MODE##_table); \
            double err = fabs(real_val - lut_val); \
            if (err > max_err) max_err = err; \
        } \
        if (max_err > (TOL) + 0.001) { \
            printf("[%s - %s] FALLITO. Errore max: %.8f, atteso <= %.8f\n", #NAME, #MODE, max_err, (double)(TOL)); \
            return 1; \
        } \
        printf("[%s - %s] PASSATO. Errore max: %.8f\n", #NAME, #MODE, max_err); \
        return 0; \
    } while (0)

#define RUN_TEST_POW2(NAME, MATH_EVAL, MIN, MAX, STEP, TOL) \
    do { \
        double max_err = 0.0; \
        double x; \
        for (x = (MIN); x <= (MAX); x += (STEP)) { \
            double real_val = (MATH_EVAL); \
            PrelookupResult kf = prelookup_pow2(x, NAME##_pow2_min, NAME##_pow2_spacing, NAME##_pow2_inv, NAME##_pow2_num, EXTRAP_CLIP); \
            double lut_val = interpolate_1d(kf, NAME##_pow2_table); \
            double err = fabs(real_val - lut_val); \
            if (err > max_err) max_err = err; \
        } \
        if (max_err > (TOL) + 0.001) { \
            printf("[%s - pow2] FALLITO. Errore max: %.8f, atteso <= %.8f\n", #NAME, max_err, (double)(TOL)); \
            return 1; \
        } \
        printf("[%s - pow2] PASSATO. Errore max: %.8f\n", #NAME, max_err); \
        return 0; \
    } while (0)

static int test_lut2d_plane(const char* mode) {
    double max_err = 0.0;
    double x, y;

    for (x = -2.0; x <= 2.0; x += 0.031) {
        for (y = -1.0; y <= 3.0; y += 0.037) {
            double real_val = 2.0 * x + 3.0 * y + 1.0;
            double lut_val;

            if (strcmp(mode, "raw") == 0) {
                lut_val = lookup2d(
                    x, y,
                    lut2d_plane_raw_row_bp,
                    lut2d_plane_raw_rows,
                    lut2d_plane_raw_col_bp,
                    lut2d_plane_raw_cols,
                    lut2d_plane_raw_table,
                    EXTRAP_CLIP,
                    EXTRAP_CLIP
                );
            } else if (strcmp(mode, "pow2") == 0) {
                lut_val = lookup2d_pow2(
                    x, y,
                    lut2d_plane_pow2_row_min,
                    lut2d_plane_pow2_row_spacing,
                    lut2d_plane_pow2_row_inv,
                    lut2d_plane_pow2_rows,
                    lut2d_plane_pow2_col_min,
                    lut2d_plane_pow2_col_spacing,
                    lut2d_plane_pow2_col_inv,
                    lut2d_plane_pow2_cols,
                    lut2d_plane_pow2_table,
                    EXTRAP_CLIP,
                    EXTRAP_CLIP
                );
            } else {
                printf("Modo 2D non valido: %s\n", mode);
                return 1;
            }

            {
                double err = fabs(real_val - lut_val);
                if (err > max_err) max_err = err;
            }
        }
    }

    if (max_err > 1e-10) {
        printf("[lut2d_plane - %s] FALLITO. Errore max %.12f\n", mode, max_err);
        return 1;
    }

    printf("[lut2d_plane - %s] PASSATO. Errore max %.12f\n", mode, max_err);
    return 0;
}

static int test_lut2d_nonlinear(const char* mode) {
    double max_err = 0.0;
    double x, y;
    const double tol = 0.01;

    for (x = -3.0; x <= 3.0; x += 0.041) {
        for (y = -2.0; y <= 2.0; y += 0.043) {
            double real_val = sin(x) + cos(y);
            double lut_val;

            if (strcmp(mode, "raw") == 0) {
                lut_val = lookup2d(
                    x, y,
                    lut2d_nonlinear_raw_row_bp,
                    lut2d_nonlinear_raw_rows,
                    lut2d_nonlinear_raw_col_bp,
                    lut2d_nonlinear_raw_cols,
                    lut2d_nonlinear_raw_table,
                    EXTRAP_CLIP,
                    EXTRAP_CLIP
                );
            } else if (strcmp(mode, "pow2") == 0) {
                lut_val = lookup2d_pow2(
                    x, y,
                    lut2d_nonlinear_pow2_row_min,
                    lut2d_nonlinear_pow2_row_spacing,
                    lut2d_nonlinear_pow2_row_inv,
                    lut2d_nonlinear_pow2_rows,
                    lut2d_nonlinear_pow2_col_min,
                    lut2d_nonlinear_pow2_col_spacing,
                    lut2d_nonlinear_pow2_col_inv,
                    lut2d_nonlinear_pow2_cols,
                    lut2d_nonlinear_pow2_table,
                    EXTRAP_CLIP,
                    EXTRAP_CLIP
                );
            } else {
                printf("Modo 2D non valido: %s\n", mode);
                return 1;
            }

            {
                double err = fabs(real_val - lut_val);
                if (err > max_err) max_err = err;
            }
        }
    }

    if (max_err > tol) {
        printf("[lut2d_nonlinear - %s] FALLITO. Errore max %.8f, atteso <= %.8f\n", mode, max_err, tol);
        return 1;
    }

    printf("[lut2d_nonlinear - %s] PASSATO. Errore max %.8f\n", mode, max_err);
    return 0;
}

int main(int argc, char** argv) {
    const char* func;
    const char* mode;

    if (argc != 3) {
        printf("Uso: %s <funzione> <modalita>\n", argv[0]);
        return 1;
    }

    func = argv[1];
    mode = argv[2];

    if (strcmp(func, "lut2d_plane") == 0) {
        return test_lut2d_plane(mode);
    }

    if (strcmp(func, "lut2d_nonlinear") == 0) {
        return test_lut2d_nonlinear(mode);
    }

#define DISPATCH(F_STR, EVAL, MIN, MAX, TOL) \
    if (strcmp(func, #F_STR) == 0) { \
        if (strcmp(mode, "raw") == 0) RUN_TEST_STD(raw, F_STR, EVAL, MIN, MAX, 0.1, 0.1); \
        else if (strcmp(mode, "greedy") == 0) RUN_TEST_STD(greedy, F_STR, EVAL, MIN, MAX, 0.01, TOL); \
        else if (strcmp(mode, "pow2") == 0) RUN_TEST_POW2(F_STR, EVAL, MIN, MAX, 0.01, TOL); \
    }

    DISPATCH(acos,  acos(x),       -1.0,   1.0,  0.02)
    DISPATCH(asin,  asin(x),       -1.0,   1.0,  0.02)
    DISPATCH(atan,  atan(x),       -5.0,   5.0,  0.02)
    DISPATCH(atan2, atan2(x, 1.0), -5.0,   5.0,  0.02)
    DISPATCH(cos,   cos(x),         0.0,   6.28, 0.02)
    DISPATCH(cosh,  cosh(x),       -3.0,   3.0,  0.05)
    DISPATCH(exp,   exp(x),         0.0,   5.0,  0.5)
    DISPATCH(log,   log(x),         0.1,   10.0, 0.05)
    DISPATCH(log10, log10(x),       0.1,   10.0, 0.05)
    DISPATCH(pow,   pow(x, 2.5),    0.0,   10.0, 0.5)
    DISPATCH(sin,   sin(x),         0.0,   6.28, 0.02)
    DISPATCH(sinh,  sinh(x),       -3.0,   3.0,  0.05)
    DISPATCH(sqrt,  sqrt(x),        0.0,  100.0, 0.1)
    DISPATCH(tan,   tan(x),        -1.4,   1.4,  0.1)
    DISPATCH(tanh,  tanh(x),       -3.0,   3.0,  0.02)

#undef DISPATCH

    printf("Errore: test %s %s non trovato.\n", func, mode);
    return 1;
}
