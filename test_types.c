#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "simulink_lookup.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define MAX_1D_POINTS 64
#define MAX_2D_ROWS 17
#define MAX_2D_COLS 19
#define MAX_2D_VALUES (MAX_2D_ROWS * MAX_2D_COLS)

/*
 * Buffer allineato per qualunque tipo supportato. I test scrivono davvero nel
 * tipo C selezionato e poi passano il relativo array void* all'API typed.
 */
typedef union {
    float f32[MAX_2D_VALUES];
    double f64[MAX_2D_VALUES];
    int8_t i8[MAX_2D_VALUES];
    uint8_t u8[MAX_2D_VALUES];
    int16_t i16[MAX_2D_VALUES];
    uint16_t u16[MAX_2D_VALUES];
    int32_t i32[MAX_2D_VALUES];
    uint32_t u32[MAX_2D_VALUES];
    int64_t i64[MAX_2D_VALUES];
    uint64_t u64[MAX_2D_VALUES];
} TypedBuffer;

typedef struct {
    const char* name;
    long double min_x;
    long double max_x;
} MathCase;

static const MathCase MATH_CASES[] = {
    {"acos",  -1.0L,   1.0L},
    {"asin",  -1.0L,   1.0L},
    {"atan",  -5.0L,   5.0L},
    {"atan2", -5.0L,   5.0L},
    {"cos",    0.0L,   6.28L},
    {"cosh",  -3.0L,   3.0L},
    {"exp",    0.0L,   5.0L},
    {"log",    0.1L,  10.0L},
    {"log10",  0.1L,  10.0L},
    {"pow",    0.0L,  10.0L},
    {"sin",    0.0L,   6.28L},
    {"sinh",  -3.0L,   3.0L},
    {"sqrt",   0.0L, 100.0L},
    {"tan",   -1.4L,   1.4L},
    {"tanh",  -3.0L,   3.0L}
};

static const size_t NUM_MATH_CASES = sizeof(MATH_CASES) / sizeof(MATH_CASES[0]);

static const void* buffer_ptr(const TypedBuffer* buffer, LutDataType type) {
    switch (type) {
        case LUT_TYPE_FLOAT32: return buffer->f32;
        case LUT_TYPE_FLOAT64: return buffer->f64;
        case LUT_TYPE_INT8: return buffer->i8;
        case LUT_TYPE_UINT8: return buffer->u8;
        case LUT_TYPE_INT16: return buffer->i16;
        case LUT_TYPE_UINT16: return buffer->u16;
        case LUT_TYPE_INT32: return buffer->i32;
        case LUT_TYPE_UINT32: return buffer->u32;
        case LUT_TYPE_INT64: return buffer->i64;
        case LUT_TYPE_UINT64: return buffer->u64;
        default: return NULL;
    }
}

static void store_value(TypedBuffer* buffer, size_t index, LutDataType type, long double value) {
    switch (type) {
        case LUT_TYPE_FLOAT32: buffer->f32[index] = (float)value; break;
        case LUT_TYPE_FLOAT64: buffer->f64[index] = (double)value; break;
        case LUT_TYPE_INT8: buffer->i8[index] = (int8_t)llroundl(value); break;
        case LUT_TYPE_UINT8: buffer->u8[index] = (uint8_t)llroundl(value); break;
        case LUT_TYPE_INT16: buffer->i16[index] = (int16_t)llroundl(value); break;
        case LUT_TYPE_UINT16: buffer->u16[index] = (uint16_t)llroundl(value); break;
        case LUT_TYPE_INT32: buffer->i32[index] = (int32_t)llroundl(value); break;
        case LUT_TYPE_UINT32: buffer->u32[index] = (uint32_t)llroundl(value); break;
        case LUT_TYPE_INT64: buffer->i64[index] = (int64_t)llroundl(value); break;
        case LUT_TYPE_UINT64: buffer->u64[index] = (uint64_t)llroundl(value); break;
        default: break;
    }
}

static long double load_value(const TypedBuffer* buffer, size_t index, LutDataType type) {
    switch (type) {
        case LUT_TYPE_FLOAT32: return (long double)buffer->f32[index];
        case LUT_TYPE_FLOAT64: return (long double)buffer->f64[index];
        case LUT_TYPE_INT8: return (long double)buffer->i8[index];
        case LUT_TYPE_UINT8: return (long double)buffer->u8[index];
        case LUT_TYPE_INT16: return (long double)buffer->i16[index];
        case LUT_TYPE_UINT16: return (long double)buffer->u16[index];
        case LUT_TYPE_INT32: return (long double)buffer->i32[index];
        case LUT_TYPE_UINT32: return (long double)buffer->u32[index];
        case LUT_TYPE_INT64: return (long double)buffer->i64[index];
        case LUT_TYPE_UINT64: return (long double)buffer->u64[index];
        default: return 0.0L;
    }
}

static long double type_tolerance(LutDataType type) {
    return type == LUT_TYPE_FLOAT32 ? 2e-5L : 2e-10L;
}

static long double eval_math(const char* name, long double x) {
    if (strcmp(name, "acos") == 0) return acosl(x);
    if (strcmp(name, "asin") == 0) return asinl(x);
    if (strcmp(name, "atan") == 0) return atanl(x);
    if (strcmp(name, "atan2") == 0) return atan2l(x, 1.0L);
    if (strcmp(name, "cos") == 0) return cosl(x);
    if (strcmp(name, "cosh") == 0) return coshl(x);
    if (strcmp(name, "exp") == 0) return expl(x);
    if (strcmp(name, "log") == 0) return logl(x);
    if (strcmp(name, "log10") == 0) return log10l(x);
    if (strcmp(name, "pow") == 0) return powl(x, 2.5L);
    if (strcmp(name, "sin") == 0) return sinl(x);
    if (strcmp(name, "sinh") == 0) return sinhl(x);
    if (strcmp(name, "sqrt") == 0) return sqrtl(x);
    if (strcmp(name, "tan") == 0) return tanl(x);
    if (strcmp(name, "tanh") == 0) return tanhl(x);
    return NAN;
}

static const MathCase* find_math_case(const char* name) {
    size_t i;
    for (i = 0; i < NUM_MATH_CASES; ++i) {
        if (strcmp(MATH_CASES[i].name, name) == 0) return &MATH_CASES[i];
    }
    return NULL;
}

static PrelookupResult reference_prelookup(
    long double u,
    const TypedBuffer* bp,
    int n,
    LutDataType type,
    ExtrapMethod extrap
) {
    PrelookupResult r;
    int k;
    long double first = load_value(bp, 0U, type);
    long double last = load_value(bp, (size_t)(n - 1), type);
    long double lower;
    long double upper;

    if (u <= first) {
        k = 0;
    } else if (u >= last) {
        k = n - 2;
    } else {
        int low = 0;
        int high = n - 1;
        while (low < high - 1) {
            int mid = low + (high - low) / 2;
            if (u < load_value(bp, (size_t)mid, type)) high = mid;
            else low = mid;
        }
        k = low;
    }

    lower = load_value(bp, (size_t)k, type);
    upper = load_value(bp, (size_t)(k + 1), type);
    r.k = k;
    if (u <= first && extrap == EXTRAP_CLIP) r.f = 0.0;
    else if (u >= last && extrap == EXTRAP_CLIP) r.f = 1.0;
    else r.f = (double)((u - lower) / (upper - lower));
    return r;
}

static PrelookupResult reference_prelookup_pow2(
    long double u,
    long double x_min,
    long double spacing,
    int n,
    ExtrapMethod extrap
) {
    PrelookupResult r;
    long double x_max = x_min + (long double)(n - 1) * spacing;
    long double normalized;
    int k;

    if (u <= x_min) {
        k = 0;
        r.f = extrap == EXTRAP_CLIP ? 0.0 : (double)((u - x_min) / spacing);
    } else if (u >= x_max) {
        k = n - 2;
        r.f = extrap == EXTRAP_CLIP ? 1.0 : (double)((u - (x_min + (long double)k * spacing)) / spacing);
    } else {
        normalized = (u - x_min) / spacing;
        k = (int)floorl(normalized);
        if (k < 0) k = 0;
        if (k > n - 2) k = n - 2;
        r.f = (double)(normalized - (long double)k);
    }
    r.k = k;
    return r;
}

static long double reference_interp1d(PrelookupResult kf, const TypedBuffer* table, LutDataType type) {
    long double y0 = load_value(table, (size_t)kf.k, type);
    long double y1 = load_value(table, (size_t)(kf.k + 1), type);
    return y0 + (long double)kf.f * (y1 - y0);
}

static long double reference_interp2d(
    PrelookupResult kr,
    PrelookupResult kc,
    const TypedBuffer* table,
    int cols,
    LutDataType type
) {
    size_t i00 = (size_t)kr.k * (size_t)cols + (size_t)kc.k;
    size_t i10 = (size_t)(kr.k + 1) * (size_t)cols + (size_t)kc.k;
    size_t i01 = (size_t)kr.k * (size_t)cols + (size_t)(kc.k + 1);
    size_t i11 = (size_t)(kr.k + 1) * (size_t)cols + (size_t)(kc.k + 1);
    long double z00 = load_value(table, i00, type);
    long double z10 = load_value(table, i10, type);
    long double z01 = load_value(table, i01, type);
    long double z11 = load_value(table, i11, type);
    long double z0 = z00 + (long double)kr.f * (z10 - z00);
    long double z1 = z01 + (long double)kr.f * (z11 - z01);
    return z0 + (long double)kc.f * (z1 - z0);
}

static int check_near(const char* label, long double actual, long double expected, long double tol) {
    long double err = fabsl(actual - expected);
    if (err > tol) {
        printf("FALLITO %s: actual=%.18Lg expected=%.18Lg err=%.18Lg tol=%.18Lg\n",
               label, actual, expected, err, tol);
        return 1;
    }
    return 0;
}

static void build_1d_dataset(
    const MathCase* mc,
    const char* mode,
    LutDataType bp_type,
    LutDataType table_type,
    TypedBuffer* bp,
    TypedBuffer* table,
    int* n_out,
    long double* pow2_min,
    long double* pow2_spacing
) {
    int i;
    int n = 33;
    long double xcoords[MAX_1D_POINTS];
    long double yvals[MAX_1D_POINTS];
    long double ymin = 0.0L;
    long double ymax = 0.0L;
    long double xmax;

    if (strcmp(mode, "greedy") == 0) {
        xcoords[0] = 0.0L;
        for (i = 1; i < n; ++i) {
            /* griglia volutamente non uniforme, sempre strettamente crescente */
            xcoords[i] = xcoords[i - 1] + (long double)(1 + (i % 3));
        }
    } else {
        for (i = 0; i < n; ++i) xcoords[i] = (long double)(2 * i);
    }

    xmax = xcoords[n - 1];
    for (i = 0; i < n; ++i) {
        long double physical_x = mc->min_x + (mc->max_x - mc->min_x) * (xcoords[i] / xmax);
        yvals[i] = eval_math(mc->name, physical_x);
        if (i == 0 || yvals[i] < ymin) ymin = yvals[i];
        if (i == 0 || yvals[i] > ymax) ymax = yvals[i];
    }

    for (i = 0; i < n; ++i) {
        long double encoded_y;
        if (ymax > ymin) encoded_y = 8.0L + 112.0L * (yvals[i] - ymin) / (ymax - ymin);
        else encoded_y = 64.0L;
        store_value(bp, (size_t)i, bp_type, xcoords[i]);
        store_value(table, (size_t)i, table_type, encoded_y);
    }

    *n_out = n;
    *pow2_min = 0.0L;
    *pow2_spacing = 2.0L;
}

static int run_1d_case(
    LutDataType bp_type,
    const char* bp_type_name,
    LutDataType table_type,
    const char* table_type_name,
    const char* func,
    const char* mode
) {
    const MathCase* mc = find_math_case(func);
    TypedBuffer bp;
    TypedBuffer table;
    int n;
    long double p2_min;
    long double p2_spacing;
    long double p2_inv;
    long double first;
    long double last;
    long double tol = type_tolerance(table_type);
    long double fraction_tol = bp_type == LUT_TYPE_FLOAT32 ? 2e-6L : 2e-12L;
    int sample;
    LutStatus status;

    if (mc == NULL) {
        printf("Funzione non riconosciuta: %s\n", func);
        return 1;
    }
    if (strcmp(mode, "raw") != 0 && strcmp(mode, "greedy") != 0 && strcmp(mode, "pow2") != 0) {
        printf("Modo 1D non riconosciuto: %s\n", mode);
        return 1;
    }

    build_1d_dataset(mc, mode, bp_type, table_type, &bp, &table, &n, &p2_min, &p2_spacing);
    p2_inv = 1.0L / p2_spacing;

    status = validate_breakpoints_typed(buffer_ptr(&bp, bp_type), n, bp_type);
    if (status != LUT_OK) {
        printf("FALLITO [input=%s/output=%s/%s/%s] validate_breakpoints: %s\n",
               bp_type_name, table_type_name, func, mode, lut_status_string(status));
        return 1;
    }

    first = load_value(&bp, 0U, bp_type);
    last = load_value(&bp, (size_t)(n - 1), bp_type);

    /* 257 campioni includono punti interni, frazionari e i due bordi. */
    for (sample = 0; sample <= 256; ++sample) {
        long double u = first + (last - first) * (long double)sample / 256.0L;
        PrelookupResult got_kf;
        PrelookupResult ref_kf;
        long double got_y;
        long double ref_y;

        if (strcmp(mode, "pow2") == 0) {
            status = prelookup_pow2_typed(u, p2_min, p2_spacing, p2_inv, n, EXTRAP_CLIP, &got_kf);
            ref_kf = reference_prelookup_pow2(u, p2_min, p2_spacing, n, EXTRAP_CLIP);
        } else {
            status = prelookup_typed(u, buffer_ptr(&bp, bp_type), n, bp_type, EXTRAP_CLIP, &got_kf);
            ref_kf = reference_prelookup(u, &bp, n, bp_type, EXTRAP_CLIP);
        }
        if (status != LUT_OK) {
            printf("FALLITO [input=%s/output=%s/%s/%s] prelookup: %s\n",
                   bp_type_name, table_type_name, func, mode, lut_status_string(status));
            return 1;
        }
        if (got_kf.k != ref_kf.k || check_near("fraction", got_kf.f, ref_kf.f, fraction_tol)) return 1;

        status = interpolate_1d_typed(got_kf, buffer_ptr(&table, table_type), n, table_type, &got_y);
        if (status != LUT_OK) {
            printf("FALLITO [input=%s/output=%s/%s/%s] interpolate: %s\n",
                   bp_type_name, table_type_name, func, mode, lut_status_string(status));
            return 1;
        }
        ref_y = reference_interp1d(ref_kf, &table, table_type);
        if (check_near("interpolate_1d", got_y, ref_y, tol)) return 1;
    }

    /* Verifica anche clipping fuori range, utile soprattutto per signed/unsigned. */
    {
        const long double outside[2] = {first - 3.25L, last + 4.75L};
        int i;
        for (i = 0; i < 2; ++i) {
            PrelookupResult got_kf;
            PrelookupResult ref_kf;
            long double got_y;
            long double ref_y;
            if (strcmp(mode, "pow2") == 0) {
                status = prelookup_pow2_typed(outside[i], p2_min, p2_spacing, p2_inv, n, EXTRAP_CLIP, &got_kf);
                ref_kf = reference_prelookup_pow2(outside[i], p2_min, p2_spacing, n, EXTRAP_CLIP);
            } else {
                status = prelookup_typed(outside[i], buffer_ptr(&bp, bp_type), n, bp_type, EXTRAP_CLIP, &got_kf);
                ref_kf = reference_prelookup(outside[i], &bp, n, bp_type, EXTRAP_CLIP);
            }
            if (status != LUT_OK) return 1;
            status = interpolate_1d_typed(got_kf, buffer_ptr(&table, table_type), n, table_type, &got_y);
            if (status != LUT_OK) return 1;
            ref_y = reference_interp1d(ref_kf, &table, table_type);
            if (check_near("clip_1d", got_y, ref_y, tol)) return 1;
        }
    }

    printf("[typed49 - input=%s - output=%s - %s - %s] PASSATO\n",
           bp_type_name, table_type_name, func, mode);
    return 0;
}

static void build_2d_dataset(
    int nonlinear,
    int pow2,
    LutDataType bp_type,
    LutDataType table_type,
    TypedBuffer* row_bp,
    TypedBuffer* col_bp,
    TypedBuffer* table,
    int* rows_out,
    int* cols_out,
    long double* row_spacing,
    long double* col_spacing
) {
    int rows = MAX_2D_ROWS;
    int cols = MAX_2D_COLS;
    long double zvals[MAX_2D_VALUES];
    long double zmin = 0.0L;
    long double zmax = 0.0L;
    int r;
    int c;

    (void)pow2;
    *row_spacing = 2.0L;
    *col_spacing = 2.0L;

    for (r = 0; r < rows; ++r) store_value(row_bp, (size_t)r, bp_type, (long double)(2 * r));
    for (c = 0; c < cols; ++c) store_value(col_bp, (size_t)c, bp_type, (long double)(2 * c));

    for (r = 0; r < rows; ++r) {
        for (c = 0; c < cols; ++c) {
            long double xr = -2.0L + 4.0L * (long double)r / (long double)(rows - 1);
            long double yc = -1.0L + 4.0L * (long double)c / (long double)(cols - 1);
            long double z = nonlinear ? sinl(1.3L * xr) + cosl(0.7L * yc)
                                      : 2.0L * xr + 3.0L * yc + 1.0L;
            size_t idx = (size_t)r * (size_t)cols + (size_t)c;
            zvals[idx] = z;
            if (idx == 0U || z < zmin) zmin = z;
            if (idx == 0U || z > zmax) zmax = z;
        }
    }

    for (r = 0; r < rows; ++r) {
        for (c = 0; c < cols; ++c) {
            size_t idx = (size_t)r * (size_t)cols + (size_t)c;
            long double encoded = zmax > zmin ? 8.0L + 112.0L * (zvals[idx] - zmin) / (zmax - zmin) : 64.0L;
            store_value(table, idx, table_type, encoded);
        }
    }

    *rows_out = rows;
    *cols_out = cols;
}

static int run_2d_case(
    LutDataType bp_type,
    const char* bp_type_name,
    LutDataType table_type,
    const char* table_type_name,
    const char* which,
    const char* mode
) {
    int nonlinear = strcmp(which, "lut2d_nonlinear") == 0;
    int pow2 = strcmp(mode, "pow2") == 0;
    TypedBuffer row_bp;
    TypedBuffer col_bp;
    TypedBuffer table;
    int rows;
    int cols;
    long double row_spacing;
    long double col_spacing;
    long double tol = type_tolerance(table_type) * 4.0L;
    int ir;
    int ic;

    if (!nonlinear && strcmp(which, "lut2d_plane") != 0) {
        printf("Caso 2D non riconosciuto: %s\n", which);
        return 1;
    }
    if (!pow2 && strcmp(mode, "raw") != 0) {
        printf("Modo 2D non riconosciuto: %s\n", mode);
        return 1;
    }

    build_2d_dataset(nonlinear, pow2, bp_type, table_type, &row_bp, &col_bp, &table,
                     &rows, &cols, &row_spacing, &col_spacing);

    if (validate_breakpoints_typed(buffer_ptr(&row_bp, bp_type), rows, bp_type) != LUT_OK) return 1;
    if (validate_breakpoints_typed(buffer_ptr(&col_bp, bp_type), cols, bp_type) != LUT_OK) return 1;

    for (ir = 0; ir <= 43; ++ir) {
        long double u_row = -1.25L + (long double)(2 * (rows - 1) + 2) * (long double)ir / 43.0L;
        for (ic = 0; ic <= 37; ++ic) {
            long double u_col = -0.75L + (long double)(2 * (cols - 1) + 1) * (long double)ic / 37.0L;
            PrelookupResult rr;
            PrelookupResult rc;
            long double expected;
            long double actual;
            LutStatus status;

            if (pow2) {
                rr = reference_prelookup_pow2(u_row, 0.0L, row_spacing, rows, EXTRAP_CLIP);
                rc = reference_prelookup_pow2(u_col, 0.0L, col_spacing, cols, EXTRAP_CLIP);
                status = lookup2d_pow2_typed(
                    u_row, u_col,
                    0.0L, row_spacing, 1.0L / row_spacing, rows,
                    0.0L, col_spacing, 1.0L / col_spacing, cols,
                    buffer_ptr(&table, table_type), table_type,
                    EXTRAP_CLIP, EXTRAP_CLIP, &actual);
            } else {
                rr = reference_prelookup(u_row, &row_bp, rows, bp_type, EXTRAP_CLIP);
                rc = reference_prelookup(u_col, &col_bp, cols, bp_type, EXTRAP_CLIP);
                status = lookup2d_typed(
                    u_row, u_col,
                    buffer_ptr(&row_bp, bp_type), rows, bp_type,
                    buffer_ptr(&col_bp, bp_type), cols, bp_type,
                    buffer_ptr(&table, table_type), table_type,
                    EXTRAP_CLIP, EXTRAP_CLIP, &actual);
            }
            if (status != LUT_OK) {
                printf("FALLITO [input=%s/output=%s/%s/%s] lookup2d: %s\n",
                       bp_type_name, table_type_name, which, mode, lut_status_string(status));
                return 1;
            }
            expected = reference_interp2d(rr, rc, &table, cols, table_type);
            if (check_near("lookup2d", actual, expected, tol)) return 1;
        }
    }

    printf("[typed49 - input=%s - output=%s - %s - %s] PASSATO\n",
           bp_type_name, table_type_name, which, mode);
    return 0;
}

static int test_errors_for_type(LutDataType type, const char* type_name) {
    TypedBuffer bp;
    TypedBuffer table;
    PrelookupResult kf;
    long double output;
    int i;

    for (i = 0; i < 4; ++i) {
        store_value(&bp, (size_t)i, type, (long double)(2 * i));
        store_value(&table, (size_t)i, type, (long double)(10 * i));
    }
    /* Duplicato intenzionale. */
    store_value(&bp, 2U, type, load_value(&bp, 1U, type));

    if (validate_breakpoints_typed(NULL, 4, type) != LUT_ERR_NULL_PTR) return 1;
    if (validate_breakpoints_typed(buffer_ptr(&bp, type), 1, type) != LUT_ERR_SIZE) return 1;
    if (validate_breakpoints_typed(buffer_ptr(&bp, type), 4, type) != LUT_ERR_NON_MONOTONIC) return 1;
    if (validate_breakpoints_typed(buffer_ptr(&table, type), 4, (LutDataType)999) != LUT_ERR_BAD_TYPE) return 1;
    if (prelookup_pow2_typed(1.0L, 0.0L, 0.0L, 1.0L, 4, EXTRAP_CLIP, &kf) != LUT_ERR_BAD_SPACING) return 1;
    if (prelookup_pow2_typed(NAN, 0.0L, 2.0L, 0.5L, 4, EXTRAP_CLIP, &kf) != LUT_ERR_NON_FINITE) return 1;
    if (prelookup_typed(1.0L, buffer_ptr(&table, type), 4, type, EXTRAP_CLIP, NULL) != LUT_ERR_NULL_PTR) return 1;

    kf.k = 3;
    kf.f = 0.5;
    if (interpolate_1d_typed(kf, buffer_ptr(&table, type), 4, type, &output) != LUT_ERR_INDEX) return 1;
    if (interpolate_1d_typed(kf, buffer_ptr(&table, type), 4, type, NULL) != LUT_ERR_NULL_PTR) return 1;

    if (type == LUT_TYPE_FLOAT32) {
        bp.f32[1] = NAN;
        if (validate_breakpoints_typed(bp.f32, 4, type) != LUT_ERR_NON_FINITE) return 1;
    } else if (type == LUT_TYPE_FLOAT64) {
        bp.f64[1] = INFINITY;
        if (validate_breakpoints_typed(bp.f64, 4, type) != LUT_ERR_NON_FINITE) return 1;
    }

    printf("[typed-errors - %s] PASSATO\n", type_name);
    return 0;
}

static int parse_type(const char* name, LutDataType* type) {
    if (strcmp(name, "float32") == 0) *type = LUT_TYPE_FLOAT32;
    else if (strcmp(name, "float64") == 0) *type = LUT_TYPE_FLOAT64;
    else if (strcmp(name, "int8") == 0) *type = LUT_TYPE_INT8;
    else if (strcmp(name, "uint8") == 0) *type = LUT_TYPE_UINT8;
    else if (strcmp(name, "int16") == 0) *type = LUT_TYPE_INT16;
    else if (strcmp(name, "uint16") == 0) *type = LUT_TYPE_UINT16;
    else if (strcmp(name, "int32") == 0) *type = LUT_TYPE_INT32;
    else if (strcmp(name, "uint32") == 0) *type = LUT_TYPE_UINT32;
    else if (strcmp(name, "int64") == 0) *type = LUT_TYPE_INT64;
    else if (strcmp(name, "uint64") == 0) *type = LUT_TYPE_UINT64;
    else return 0;
    return 1;
}

int main(int argc, char** argv) {
    LutDataType bp_type;
    LutDataType table_type;
    const char* bp_type_name;
    const char* table_type_name;
    const char* test_name;
    const char* mode;

    if (argc < 3) {
        printf("Uso legacy: %s <tipo> <funzione|errors> [modalita]\n", argv[0]);
        printf("Uso mixed:  %s <tipo_input> <tipo_output> <funzione> <modalita>\n", argv[0]);
        return 1;
    }

    bp_type_name = argv[1];
    if (!parse_type(bp_type_name, &bp_type)) {
        printf("Tipo input test non riconosciuto: %s\n", bp_type_name);
        return 1;
    }

    /* Interfaccia storica: <tipo> errors oppure <tipo> <test> <modo>. */
    if (strcmp(argv[2], "errors") == 0) {
        return test_errors_for_type(bp_type, bp_type_name);
    }
    if (argc == 4) {
        table_type = bp_type;
        table_type_name = bp_type_name;
        test_name = argv[2];
        mode = argv[3];
    } else if (argc == 5) {
        table_type_name = argv[2];
        if (!parse_type(table_type_name, &table_type)) {
            printf("Tipo output test non riconosciuto: %s\n", table_type_name);
            return 1;
        }
        test_name = argv[3];
        mode = argv[4];
    } else {
        printf("Argomenti non validi.\n");
        return 1;
    }

    if (strncmp(test_name, "lut2d_", 6) == 0) {
        return run_2d_case(
            bp_type, bp_type_name, table_type, table_type_name, test_name, mode
        );
    }
    return run_1d_case(
        bp_type, bp_type_name, table_type, table_type_name, test_name, mode
    );
}
