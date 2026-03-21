#include <stdio.h>
#include "simulink_lookup.h"

int main() {
    // ==========================================
    // Example 1: 1D Lookup Table pipeline
    // ==========================================
    printf("--- 1D Interpolation Pipeline ---\n");
    const double bp_1d[]    = {0.0, 10.0, 20.0, 30.0};
    const double table_1d[] = {0.0, 100.0, 400.0, 900.0}; // e.g., y = x^2
    int num_pts_1d = sizeof(bp_1d) / sizeof(bp_1d[0]);

    double input_1d = 15.0; // Right in the middle of 10 and 20

    // Step 1: Prelookup
    PrelookupResult kf_1d = prelookup(input_1d, bp_1d, num_pts_1d, EXTRAP_LINEAR);
    
    // Step 2: Interpolate
    double output_1d = interpolate_1d(kf_1d, table_1d);
    
    printf("Input: %.1f -> Output: %.1f\n\n", input_1d, output_1d);


    // ==========================================
    // Example 2: 2D Lookup Table pipeline
    // ==========================================
    printf("--- 2D Interpolation Pipeline ---\n");
    const double bp_row[] = {1.0, 2.0, 3.0}; // e.g., Engine Speed
    const double bp_col[] = {10.0, 20.0};    // e.g., Throttle Position
    
    int num_rows = sizeof(bp_row) / sizeof(bp_row[0]);
    int num_cols = sizeof(bp_col) / sizeof(bp_col[0]);

    // Flattened 2D array (3 rows x 2 columns)
    const double table_2d[] = {
        100.0, 200.0,  // Row 0
        150.0, 250.0,  // Row 1
        300.0, 400.0   // Row 2
    };

    double input_row = 1.5; // Halfway between Row 0 and Row 1
    double input_col = 15.0; // Halfway between Col 0 and Col 1

    // Step 1: Prelookup for both dimensions
    PrelookupResult kf_row = prelookup(input_row, bp_row, num_rows, EXTRAP_CLIP);
    PrelookupResult kf_col = prelookup(input_col, bp_col, num_cols, EXTRAP_CLIP);

    // Step 2: Interpolate 2D
    double output_2d = interpolate_2d(kf_row, kf_col, table_2d, num_cols);

    printf("Input (Row=%.1f, Col=%.1f) -> Output: %.1f\n", input_row, input_col, output_2d);

    return 0;
}