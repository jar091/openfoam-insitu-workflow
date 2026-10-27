cmake_minimum_required(VERSION 3.20)
project(anari_barney_tests LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(anari REQUIRED)
find_package(MPI REQUIRED COMPONENTS CXX)

# stb_image_write from the ANARI-SDK source tree (header only)
set(STB_DIR ${CMAKE_CURRENT_LIST_DIR}/../../src/ANARI-SDK/external/stb_image)

add_executable(anariBarneyTest anariBarneyTest.cpp)
target_include_directories(anariBarneyTest PRIVATE ${STB_DIR})
target_link_libraries(anariBarneyTest PRIVATE anari::anari MPI::MPI_CXX)
target_compile_definitions(anariBarneyTest PRIVATE WITH_MPI=1)
