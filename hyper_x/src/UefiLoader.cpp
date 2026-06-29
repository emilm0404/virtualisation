#include "../include/UefiLoader.h"
#include <fstream>
#include <iostream>
#include <cstring>

#if defined(_WIN32) || defined(_WIN64)
#include <windows.h>
#else
#include <sys/mman.h>
#endif

bool load_uefi_firmware(
    const std::string& firmware_path,
    UefiFirmwareInfo& info
) {
    std::ifstream fw(firmware_path, std::ios::binary | std::ios::ate);
    if (!fw.is_open()) {
        std::cerr << "uefi-loader: failed to open firmware image: " << firmware_path << std::endl;
        return false;
    }

    size_t file_size = fw.tellg();
    fw.seekg(0, std::ios::beg);

    // OVMF.fd is typically 2MB (0x200000) or 4MB (0x400000).
    // The firmware ROM must be mapped to the top of the 32-bit address space
    // so that the x86 reset vector (0xFFFFFFF0) falls inside the ROM.
    // For a 2MB ROM: GPA = 0x100000000 - 0x200000 = 0xFFE00000
    // For a 4MB ROM: GPA = 0x100000000 - 0x400000 = 0xFFC00000
    if (file_size != 0x200000 && file_size != 0x400000 && file_size != 0x100000) {
        std::cerr << "uefi-loader: warning: unusual firmware size " << file_size 
                  << " bytes. Expected 1MB, 2MB, or 4MB." << std::endl;
    }

    // Calculate GPA: align firmware to top of 4GB
    info.rom_gpa = 0x100000000ULL - file_size;
    info.rom_size = file_size;

    // Allocate host memory for the ROM
#if defined(_WIN32) || defined(_WIN64)
    info.rom_host_addr = VirtualAlloc(nullptr, file_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
#else
    info.rom_host_addr = mmap(NULL, file_size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (info.rom_host_addr == MAP_FAILED) info.rom_host_addr = nullptr;
#endif

    if (!info.rom_host_addr) {
        std::cerr << "uefi-loader: failed to allocate host memory for firmware ROM." << std::endl;
        return false;
    }

    // Read firmware image into host memory
    fw.read(reinterpret_cast<char*>(info.rom_host_addr), file_size);
    if (static_cast<size_t>(fw.gcount()) != file_size) {
        std::cerr << "uefi-loader: failed to read complete firmware image." << std::endl;
        free_uefi_firmware(info);
        return false;
    }

    std::cout << "uefi-loader: loaded firmware image (" << file_size << " bytes) "
              << "mapped at GPA 0x" << std::hex << info.rom_gpa << std::dec << std::endl;

    // Allocate 256KB NVRAM region for UEFI variable storage (pflash1)
    // Map it just below the firmware ROM
    info.nvram_size = 0x40000; // 256KB
    info.nvram_gpa = info.rom_gpa - info.nvram_size;

#if defined(_WIN32) || defined(_WIN64)
    info.nvram_host_addr = VirtualAlloc(nullptr, info.nvram_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
#else
    info.nvram_host_addr = mmap(NULL, info.nvram_size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (info.nvram_host_addr == MAP_FAILED) info.nvram_host_addr = nullptr;
#endif

    if (!info.nvram_host_addr) {
        std::cerr << "uefi-loader: failed to allocate NVRAM region." << std::endl;
        free_uefi_firmware(info);
        return false;
    }

    // Initialize NVRAM to 0xFF (emulates unprogrammed flash)
    std::memset(info.nvram_host_addr, 0xFF, info.nvram_size);

    std::cout << "uefi-loader: NVRAM region (" << info.nvram_size << " bytes) "
              << "at GPA 0x" << std::hex << info.nvram_gpa << std::dec << std::endl;

    return true;
}

void free_uefi_firmware(UefiFirmwareInfo& info) {
#if defined(_WIN32) || defined(_WIN64)
    if (info.rom_host_addr) {
        VirtualFree(info.rom_host_addr, 0, MEM_RELEASE);
        info.rom_host_addr = nullptr;
    }
    if (info.nvram_host_addr) {
        VirtualFree(info.nvram_host_addr, 0, MEM_RELEASE);
        info.nvram_host_addr = nullptr;
    }
#else
    if (info.rom_host_addr) {
        munmap(info.rom_host_addr, info.rom_size);
        info.rom_host_addr = nullptr;
    }
    if (info.nvram_host_addr) {
        munmap(info.nvram_host_addr, info.nvram_size);
        info.nvram_host_addr = nullptr;
    }
#endif
}
