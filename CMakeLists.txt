cmake_minimum_required(VERSION 3.10)
project(SimulinkLookup C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED TRUE)

# --- 1. LIBRERIA PRINCIPALE ---
add_library(simulink_lookup simulink_lookup.c)
target_include_directories(simulink_lookup PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

if(UNIX AND NOT APPLE)
    target_link_libraries(simulink_lookup PUBLIC m)
endif()

# --- 2. PYTHON PER AUTOGENERAZIONE ---
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/.venv/bin/python")
    set(Python3_EXECUTABLE "${CMAKE_CURRENT_SOURCE_DIR}/.venv/bin/python")
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/.venv/Scripts/python.exe")
    set(Python3_EXECUTABLE "${CMAKE_CURRENT_SOURCE_DIR}/.venv/Scripts/python.exe")
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(GENERATED_HEADER "${CMAKE_CURRENT_BINARY_DIR}/test_luts_data.h")

add_custom_command(
    OUTPUT ${GENERATED_HEADER}
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/lut_autogen.py
            --output ${GENERATED_HEADER}
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/lut_autogen.py
    COMMENT "Generazione automatica LUT 1D/2D via Python..."
    VERBATIM
)

add_custom_target(generate_luts DEPENDS ${GENERATED_HEADER})

# --- 3. ESEGUIBILE DI TEST ---
add_executable(run_math_tests test_luts.c ${GENERATED_HEADER})
add_dependencies(run_math_tests generate_luts)

target_link_libraries(run_math_tests PRIVATE simulink_lookup)
if(UNIX AND NOT APPLE)
    target_link_libraries(run_math_tests PRIVATE m)
endif()

target_include_directories(run_math_tests PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_BINARY_DIR}
)

# --- 4. CTEST ---
enable_testing()

set(MATH_FUNCS
    acos asin atan atan2 cos cosh exp log log10 pow sin sinh sqrt tan tanh
)

set(MODES raw greedy pow2)

foreach(func IN LISTS MATH_FUNCS)
    foreach(mode IN LISTS MODES)
        add_test(NAME "TestLUT1D_${func}_${mode}"
                 COMMAND run_math_tests ${func} ${mode})
    endforeach()
endforeach()

# Test 2D aggiuntivi
add_test(NAME TestLUT2D_plane_raw     COMMAND run_math_tests lut2d_plane raw)
add_test(NAME TestLUT2D_plane_pow2    COMMAND run_math_tests lut2d_plane pow2)
add_test(NAME TestLUT2D_nonlinear_raw COMMAND run_math_tests lut2d_nonlinear raw)
add_test(NAME TestLUT2D_nonlinear_pow2 COMMAND run_math_tests lut2d_nonlinear pow2)

# --- 5. TEST API TYPED: replica dei 49 scenari per OGNI tipo ---
# 15 funzioni x 3 modalita' = 45, piu' 4 casi 2D = 49 test per tipo.
# Con 10 tipi: 490 test typed distinti, cosi' CTest identifica subito
# tipo/funzione/modalita' che eventualmente regredisce.
add_executable(run_type_tests test_types.c)
target_link_libraries(run_type_tests PRIVATE simulink_lookup)
if(UNIX AND NOT APPLE)
    target_link_libraries(run_type_tests PRIVATE m)
endif()
target_include_directories(run_type_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

set(LUT_DATA_TYPES
    float32 float64
    int8 uint8 int16 uint16 int32 uint32 int64 uint64
)

foreach(data_type IN LISTS LUT_DATA_TYPES)
    foreach(func IN LISTS MATH_FUNCS)
        foreach(mode IN LISTS MODES)
            add_test(NAME "TestTyped49_${data_type}_${func}_${mode}"
                     COMMAND run_type_tests ${data_type} ${func} ${mode})
        endforeach()
    endforeach()

    add_test(NAME "TestTyped49_${data_type}_lut2d_plane_raw"
             COMMAND run_type_tests ${data_type} lut2d_plane raw)
    add_test(NAME "TestTyped49_${data_type}_lut2d_plane_pow2"
             COMMAND run_type_tests ${data_type} lut2d_plane pow2)
    add_test(NAME "TestTyped49_${data_type}_lut2d_nonlinear_raw"
             COMMAND run_type_tests ${data_type} lut2d_nonlinear raw)
    add_test(NAME "TestTyped49_${data_type}_lut2d_nonlinear_pow2"
             COMMAND run_type_tests ${data_type} lut2d_nonlinear pow2)

    # Error-path separato per ogni tipo (oltre ai 49), incluse le peculiarita'
    # NaN/Inf per float e monotonicita'/indici per gli interi.
    add_test(NAME "TestTypedErrors_${data_type}"
             COMMAND run_type_tests ${data_type} errors)
endforeach()

# --- 5b. TEST MIXED INPUT/OUTPUT: 49 scenari per ogni coppia diversa ---
# La GUI permette di scegliere indipendentemente il tipo dei breakpoint/input
# e il tipo della tabella/output. Le 90 coppie eterogenee (10 x 9) vengono
# quindi provate sugli stessi 49 scenari usati per i tipi omogenei:
# 90 x 49 = 4410 test runtime C aggiuntivi.
foreach(input_type IN LISTS LUT_DATA_TYPES)
    foreach(output_type IN LISTS LUT_DATA_TYPES)
        if(NOT input_type STREQUAL output_type)
            foreach(func IN LISTS MATH_FUNCS)
                foreach(mode IN LISTS MODES)
                    add_test(
                        NAME "TestTypedMixed49_${input_type}_to_${output_type}_${func}_${mode}"
                        COMMAND run_type_tests ${input_type} ${output_type} ${func} ${mode}
                    )
                    set_tests_properties(
                        "TestTypedMixed49_${input_type}_to_${output_type}_${func}_${mode}"
                        PROPERTIES LABELS "typed_mixed;input_${input_type};output_${output_type}"
                    )
                endforeach()
            endforeach()

            foreach(case_name IN ITEMS lut2d_plane lut2d_nonlinear)
                foreach(mode IN ITEMS raw pow2)
                    add_test(
                        NAME "TestTypedMixed49_${input_type}_to_${output_type}_${case_name}_${mode}"
                        COMMAND run_type_tests ${input_type} ${output_type} ${case_name} ${mode}
                    )
                    set_tests_properties(
                        "TestTypedMixed49_${input_type}_to_${output_type}_${case_name}_${mode}"
                        PROPERTIES LABELS "typed_mixed;input_${input_type};output_${output_type}"
                    )
                endforeach()
            endforeach()
        endif()
    endforeach()
endforeach()

# --- 6. TEST GENERATORE GUI / QUANTIZZAZIONE ---
add_test(
    NAME TestCodegen_types_and_errors
    COMMAND ${Python3_EXECUTABLE} -m unittest -v test_codegen_types.py
)
set_tests_properties(TestCodegen_types_and_errors PROPERTIES
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)

# Genera C usando tutte le 10x10 combinazioni breakpoint/tabella, sia raw sia
# EvenPow2Spacing, e lo compila durante la build. Questo intercetta mismatch tra
# la GUI Python e le firme reali dell'API C.
set(GENERATED_TYPED_SMOKE "${CMAKE_CURRENT_BINARY_DIR}/generated_typed_codegen_smoke.c")
add_custom_command(
    OUTPUT ${GENERATED_TYPED_SMOKE}
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/generate_codegen_compile_fixture.py
            --output ${GENERATED_TYPED_SMOKE}
    DEPENDS
        ${CMAKE_CURRENT_SOURCE_DIR}/generate_codegen_compile_fixture.py
        ${CMAKE_CURRENT_SOURCE_DIR}/lut_codegen.py
        ${CMAKE_CURRENT_SOURCE_DIR}/simulink_lookup.h
    COMMENT "Generazione smoke-test C per tutte le combinazioni di tipi LUT..."
    VERBATIM
)
add_library(typed_codegen_smoke OBJECT ${GENERATED_TYPED_SMOKE})
target_include_directories(typed_codegen_smoke PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
