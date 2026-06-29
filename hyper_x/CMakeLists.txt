cmake_minimum_required(VERSION 3.15)
project(hyper_x CXX)

set(CMAKE_CXX_STANDARD 17)

add_executable(hyper_x 
    src/main.cpp 
    src/Loader.cpp
    src/UefiLoader.cpp
    src/WhpxBackend.cpp
    src/KvmBackend.cpp
)

if(WIN32)
    target_link_libraries(hyper_x PRIVATE WinHvPlatform)
endif()

# compile guest vulkan proxy library
add_library(libvulkan_hyperx SHARED src/libvulkan_hyperx.cpp)
# disable prefix on windows so it matches standard library names
set_target_properties(libvulkan_hyperx PROPERTIES PREFIX "")
