cmake_minimum_required(VERSION 3.16)
project(skip_columns C)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Binary name matches the directory and the 'native/skip-columns' make target.
add_executable(skip-columns main.c)

# Location of the duckdb-read-stat extension relative to this directory
# (src/native/skip-columns -> <repo root>/duckdb-read-stat).
get_filename_component(READ_STAT_EXT_DIR
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../duckdb-read-stat" ABSOLUTE)

# Which extension build to link against: debug (default) or release.
# Override with: cmake -B build -DREAD_STAT_BUILD_TYPE=release
# Note: the value is cached, so reconfiguring an existing build dir keeps the
# previous choice unless -D is passed again (or the build dir is deleted).
set(READ_STAT_BUILD_TYPE "debug" CACHE STRING
    "Extension build to link against (debug or release)")

set(READ_STAT_LIBRARY
    "${READ_STAT_EXT_DIR}/build/${READ_STAT_BUILD_TYPE}/libread_stat.so")

if(NOT EXISTS "${READ_STAT_LIBRARY}")
    message(FATAL_ERROR
        "libread_stat.so not found at ${READ_STAT_LIBRARY}.\n"
        "Build the extension first, e.g. from the repository root:\n"
        "  make -C duckdb-read-stat ${READ_STAT_BUILD_TYPE}\n"
        "or pick the other build type with -DREAD_STAT_BUILD_TYPE=debug|release")
endif()

# Import the readstat shared library built by the extension.
# Because the full path is known, CMake adds the extension's build directory
# to the build RPATH, so test_bin runs without setting LD_LIBRARY_PATH.
add_library(read_stat SHARED IMPORTED)
set_target_properties(read_stat PROPERTIES
    IMPORTED_LOCATION "${READ_STAT_LIBRARY}"
    INTERFACE_INCLUDE_DIRECTORIES "${READ_STAT_EXT_DIR}/third_party/readstat/src")

# m: readstat uses math functions such as fmod
target_link_libraries(skip-columns PRIVATE read_stat m)
