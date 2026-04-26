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
