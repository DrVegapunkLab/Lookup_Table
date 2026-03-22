cmake_minimum_required(VERSION 3.10)
project(SimulinkLookup C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED True)

# --- 1. LIBRERIA PRINCIPALE ---
add_library(simulink_lookup simulink_lookup.c)
target_include_directories(simulink_lookup PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

# --- 2. AUTOMAZIONE PYTHON ---
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/.venv/bin/python")
    set(Python3_EXECUTABLE "${CMAKE_CURRENT_SOURCE_DIR}/.venv/bin/python") # Mac/Linux
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/.venv/Scripts/python.exe")
    set(Python3_EXECUTABLE "${CMAKE_CURRENT_SOURCE_DIR}/.venv/Scripts/python.exe") # Windows
endif()

find_package(Python3 REQUIRED)

add_custom_command(
    OUTPUT test_luts_data.h
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/lut_autogen.py
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/lut_autogen.py
    COMMENT "Generazione automatica delle 45 LUT matematiche via Python..."
)

# --- 3. ESEGUIBILE DI TEST ---
add_executable(run_math_tests test_luts.c test_luts_data.h)
target_link_libraries(run_math_tests simulink_lookup m)
target_include_directories(run_math_tests PRIVATE ${CMAKE_CURRENT_BINARY_DIR})

# --- 4. REGISTRAZIONE DINAMICA DEI TEST (CTEST) ---
enable_testing()

# Lista delle 15 funzioni matematiche
set(MATH_FUNCS 
    acos asin atan atan2 cos cosh exp log log10 pow sin sinh sqrt tan tanh
)
# Lista delle 3 modalità di generazione
set(MODES raw greedy pow2)

# Crea un test separato per ogni combinazione (15x3 = 45 Test)
foreach(func IN LISTS MATH_FUNCS)
    foreach(mode IN LISTS MODES)
        add_test(NAME "TestLUT_${func}_${mode}" 
                 COMMAND run_math_tests ${func} ${mode})
    endforeach()
endforeach()