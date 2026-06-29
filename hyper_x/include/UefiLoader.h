#pragma once
#include <string>
#include <cstdint>

// UEFI firmware loading for OVMF-based boot sequence.
// Maps the firmware ROM image to the top of the 32-bit physical address space
// so the x86 reset vector (0xFFFFFFF0) lands inside the firmware code.

struct UefiFirmwareInfo {
    uint64_t rom_gpa;       // GPA where firmware ROM is mapped (e.g. 0xFFE00000 for 2MB)
    size_t   rom_size;      // Size of the firmware ROM in bytes
    void*    rom_host_addr; // Host virtual address of the ROM allocation

    uint64_t nvram_gpa;       // GPA for UEFI variable storage (pflash1)
    size_t   nvram_size;      // Size of NVRAM region
    void*    nvram_host_addr; // Host virtual address of NVRAM allocation
};

// Load a UEFI firmware image (OVMF.fd or OVMF_CODE.fd) into a host memory
// allocation positioned so that GPA maps to the top of 4GB address space.
// Returns populated UefiFirmwareInfo on success.
bool load_uefi_firmware(
    const std::string& firmware_path,
    UefiFirmwareInfo& info
);

// Free host-side allocations made by load_uefi_firmware.
void free_uefi_firmware(UefiFirmwareInfo& info);
