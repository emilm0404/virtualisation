cmake_minimum_required(VERSION 3.15)
project(hyper_x CXX)

set(CMAKE_CXX_STANDARD 17)

add_executable(hyper_x main.cpp)

# link against windows hypervisor platform library
target_link_libraries(hyper_x PRIVATE WinHvPlatform)
