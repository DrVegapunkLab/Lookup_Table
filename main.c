#include <stdio.h>
#include "simulink_lookup.h"

int main() {
    printf("=== Test Libreria Simulink Lookup ===\n\n");

    // 1. TEST STANDARD (Ricerca Binaria)
    printf("1. Test Standard (Greedy / Raw)\n");
    const double bp_std[] = {0.0, 10.0, 50.0, 100.0};
    const double table_std[] = {0.0, 20.0, 80.0, 100.0};
    int num_std = 4;
    
    double in_std = 30.0;
    PrelookupResult res_std = prelookup(in_std, bp_std, num_std, EXTRAP_CLIP);
    double out_std = interpolate_1d(res_std, table_std);
    printf("Input: %.1f -> Output: %.2f (k=%d, f=%.2f)\n\n", in_std, out_std, res_std.k, res_std.f);


    // 2. TEST POW2 (Matematica Veloce)
    printf("2. Test EvenPow2Spacing (O(1))\n");
    // X_MIN = 0.0, Spacing = 2.0 (2^1)
    const int num_pow2 = 5; // Punti X impliciti: 0.0, 2.0, 4.0, 6.0, 8.0
    const double x_min = 0.0;
    const double spacing = 2.0;
    const double inv_spacing = 0.5; // 1.0 / 2.0
    const double table_pow2[] = {0.0, 10.0, 40.0, 90.0, 160.0}; // x^2 * 2.5
    
    double in_pow2 = 5.0; // Cade esattamente a metà tra 4.0 e 6.0
    PrelookupResult res_pow2 = prelookup_pow2(in_pow2, x_min, spacing, inv_spacing, num_pow2, EXTRAP_CLIP);
    double out_pow2 = interpolate_1d(res_pow2, table_pow2);
    printf("Input: %.1f -> Output: %.2f (k=%d, f=%.2f)\n", in_pow2, out_pow2, res_pow2.k, res_pow2.f);

    return 0;
}