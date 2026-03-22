#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>
#include "simulink_lookup.h"
#include "test_luts_data.h"

// Macro per eseguire il test in modalità Raw o Greedy (Prelookup standard)
#define RUN_TEST_STD(MODE, NAME, MATH_EVAL, MIN, MAX, STEP, TOL) \
    do { \
        double max_err = 0.0; \
        for(double x = MIN; x <= MAX; x += STEP) { \
            double real_val = MATH_EVAL; \
            PrelookupResult kf = prelookup(x, NAME##_##MODE##_bp, NAME##_##MODE##_num, EXTRAP_CLIP); \
            double lut_val = interpolate_1d(kf, NAME##_##MODE##_table); \
            double err = fabs(real_val - lut_val); \
            if(err > max_err) max_err = err; \
        } \
        if(max_err > TOL + 0.001) { \
            printf("[%s - %s] FALLITO! Errore max: %.4f (Atteso <= %.4f)\n", #NAME, #MODE, max_err, TOL); \
            return 1; \
        } \
        printf("[%s - %s] PASSATO. Errore max: %.4f\n", #NAME, #MODE, max_err); \
        return 0; \
    } while(0)

// Macro per eseguire il test in modalità Pow2 (Prelookup ultra-veloce math O(1))
#define RUN_TEST_POW2(NAME, MATH_EVAL, MIN, MAX, STEP, TOL) \
    do { \
        double max_err = 0.0; \
        for(double x = MIN; x <= MAX; x += STEP) { \
            double real_val = MATH_EVAL; \
            PrelookupResult kf = prelookup_pow2(x, NAME##_pow2_min, NAME##_pow2_spacing, NAME##_pow2_inv, NAME##_pow2_num, EXTRAP_CLIP); \
            double lut_val = interpolate_1d(kf, NAME##_pow2_table); \
            double err = fabs(real_val - lut_val); \
            if(err > max_err) max_err = err; \
        } \
        if(max_err > TOL + 0.001) { \
            printf("[%s - pow2] FALLITO! Errore max: %.4f (Atteso <= %.4f)\n", #NAME, max_err, TOL); \
            return 1; \
        } \
        printf("[%s - pow2] PASSATO. Errore max: %.4f\n", #NAME, max_err); \
        return 0; \
    } while(0)

// Sistema di smistamento principale
int main(int argc, char** argv) {
    if (argc != 3) {
        printf("Uso: %s <funzione> <modalita>\n", argv[0]);
        return 1;
    }
    const char* func = argv[1];
    const char* mode = argv[2];

    // Smistamento tramite Macro basato sugli argomenti del terminale
    // atan2 fissa Y=1.0, pow fissa Y=2.5 (come specificato nello script Python)
    
    #define DISPATCH(F_STR, EVAL, MIN, MAX, TOL) \
        if (strcmp(func, #F_STR) == 0) { \
            if (strcmp(mode, "raw") == 0)         RUN_TEST_STD(raw, F_STR, EVAL, MIN, MAX, 0.1, 0.1); \
            else if (strcmp(mode, "greedy") == 0) RUN_TEST_STD(greedy, F_STR, EVAL, MIN, MAX, 0.01, TOL); \
            else if (strcmp(mode, "pow2") == 0)   RUN_TEST_POW2(F_STR, EVAL, MIN, MAX, 0.01, TOL); \
        }

    //       Nome   Calcolo C          Min    Max   Tolleranza
    DISPATCH(acos,  acos(x),          -1.0,   1.0,  0.02)
    DISPATCH(asin,  asin(x),          -1.0,   1.0,  0.02)
    DISPATCH(atan,  atan(x),          -5.0,   5.0,  0.02)
    DISPATCH(atan2, atan2(x, 1.0),    -5.0,   5.0,  0.02)
    DISPATCH(cos,   cos(x),            0.0,   6.28, 0.02)
    DISPATCH(cosh,  cosh(x),          -3.0,   3.0,  0.05)
    DISPATCH(exp,   exp(x),            0.0,   5.0,  0.5)
    DISPATCH(log,   log(x),            0.1,   10.0, 0.05)
    DISPATCH(log10, log10(x),          0.1,   10.0, 0.05)
    DISPATCH(pow,   pow(x, 2.5),       0.0,   10.0, 0.5)
    DISPATCH(sin,   sin(x),            0.0,   6.28, 0.02)
    DISPATCH(sinh,  sinh(x),          -3.0,   3.0,  0.05)
    DISPATCH(sqrt,  sqrt(x),           0.0,  100.0, 0.1)
    DISPATCH(tan,   tan(x),           -1.4,   1.4,  0.1)
    DISPATCH(tanh,  tanh(x),          -3.0,   3.0,  0.02)

    printf("Errore: Test %s %s non trovato.\n", func, mode);
    return 1;
}