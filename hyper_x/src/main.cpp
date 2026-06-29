#include <iostream>
#include <memory>
#include <cstring>
#if defined(_WIN32) || defined(_WIN64)
#include <windows.h>
#else
#include <sys/mman.h>
#include <unistd.h>
#endif
#include "../include/IHypervisor.h"
#include "../include/WhpxBackend.h"
#include "../include/KvmBackend.h"
#include "../include/Loader.h"
#include "../include/UefiLoader.h"

const unsigned char GUEST_CODE[] = {
    0xB0, 0x64,
    0xE6, 0x80,
    0xF4
};

int main(int argc, char** argv) {
    std::cout << "hyper-x starting execution..." << std::endl;

    std::string kernel_path = "";
    std::string initrd_path = "";
    std::string firmware_path = "";
    size_t ram_size_mb = 128; // default 128MB for kernel boot

    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "-k") == 0 && i + 1 < argc) {
            kernel_path = argv[++i];
        } else if (std::strcmp(argv[i], "-i") == 0 && i + 1 < argc) {
            initrd_path = argv[++i];
        } else if (std::strcmp(argv[i], "-f") == 0 && i + 1 < argc) {
            firmware_path = argv[++i];
        } else if (std::strcmp(argv[i], "-m") == 0 && i + 1 < argc) {
            ram_size_mb = std::stoul(argv[++i]);
        }
    }

    // UEFI boot requires more RAM (default 512MB)
    if (!firmware_path.empty() && ram_size_mb == 128) {
        ram_size_mb = 512;
    }

    std::unique_ptr<IHypervisor> hypervisor;
#if defined(_WIN32) || defined(_WIN64)
    std::cout << "whpx: selecting windows hypervisor platform backend." << std::endl;
    hypervisor = std::make_unique<WhpxBackend>();
#else
    std::cout << "kvm: selecting linux kvm backend." << std::endl;
    hypervisor = std::make_unique<KvmBackend>();
#endif

    if (!hypervisor->initialize()) {
        std::cerr << "error: failed to initialize hypervisor platform." << std::endl;
        return 1;
    }

    if (!hypervisor->setup_vm()) {
        std::cerr << "error: failed to setup VM." << std::endl;
        return 1;
    }

    // ========================================
    // UEFI Firmware Boot Path (-f flag)
    // ========================================
    if (!firmware_path.empty()) {
        std::cout << "uefi: entering UEFI firmware boot mode." << std::endl;

        const size_t ram_size = ram_size_mb * 1024 * 1024;
        void* host_ram = nullptr;
#if defined(_WIN32) || defined(_WIN64)
        host_ram = VirtualAlloc(nullptr, ram_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
#else
        host_ram = mmap(NULL, ram_size, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
#endif
        if (!host_ram) {
            std::cerr << "error: failed to allocate " << ram_size_mb << "MB guest RAM." << std::endl;
            return 1;
        }

        // Map guest RAM at GPA 0x00000000
        if (!hypervisor->map_guest_memory(0, ram_size, host_ram, 0)) {
            std::cerr << "error: failed to map guest RAM." << std::endl;
            return 1;
        }
        std::cout << "uefi: mapped " << ram_size_mb << "MB guest RAM at GPA 0x00000000" << std::endl;

        // Load UEFI firmware ROM
        UefiFirmwareInfo fw_info = {};
        if (!load_uefi_firmware(firmware_path, fw_info)) {
            std::cerr << "error: failed to load UEFI firmware." << std::endl;
            return 1;
        }

        // Map firmware ROM into guest physical address space (slot 2)
        if (!hypervisor->map_guest_memory(fw_info.rom_gpa, fw_info.rom_size, fw_info.rom_host_addr, 2)) {
            std::cerr << "error: failed to map firmware ROM at GPA 0x" << std::hex << fw_info.rom_gpa << std::dec << std::endl;
            free_uefi_firmware(fw_info);
            return 1;
        }

        // Map NVRAM pflash region (slot 3)
        if (!hypervisor->map_guest_memory(fw_info.nvram_gpa, fw_info.nvram_size, fw_info.nvram_host_addr, 3)) {
            std::cerr << "error: failed to map NVRAM at GPA 0x" << std::hex << fw_info.nvram_gpa << std::dec << std::endl;
            free_uefi_firmware(fw_info);
            return 1;
        }

        // Map Shared VRAM (slot 1) — retained for X-GPU bridge
        const size_t vram_size = 0x10000000; // 256MB
        void* host_vram = nullptr;
#if defined(_WIN32) || defined(_WIN64)
        host_vram = VirtualAlloc(nullptr, vram_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
#else
        host_vram = mmap(NULL, vram_size, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
#endif
        if (host_vram) {
            hypervisor->map_guest_memory(0x40000000, vram_size, host_vram, 1);
        }

        // Initialize vCPU in 16-bit Real Mode (x86 reset vector)
        if (!hypervisor->setup_vcpu_realmode()) {
            std::cerr << "error: failed to configure vCPU in real mode." << std::endl;
            free_uefi_firmware(fw_info);
            return 1;
        }

        // Run the VM — OVMF firmware will boot, transition to protected/long mode,
        // and eventually drop into the EFI Shell
        if (!hypervisor->run_loop()) {
            std::cerr << "error: VM execution failed." << std::endl;
        }

        // Cleanup
        free_uefi_firmware(fw_info);
#if defined(_WIN32) || defined(_WIN64)
        if (host_vram) VirtualFree(host_vram, 0, MEM_RELEASE);
        VirtualFree(host_ram, 0, MEM_RELEASE);
#else
        if (host_vram) munmap(host_vram, vram_size);
        munmap(host_ram, ram_size);
#endif
        std::cout << "hyper-x execution completed successfully." << std::endl;
        return 0;
    }

    // ========================================
    // Direct Linux Kernel Boot Path (-k flag)
    // ========================================
    const size_t ram_size = ram_size_mb * 1024 * 1024;
    void* host_ram = nullptr;
#if defined(_WIN32) || defined(_WIN64)
    host_ram = VirtualAlloc(nullptr, ram_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
#else
    host_ram = mmap(NULL, ram_size, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
#endif

    if (!host_ram) {
        std::cerr << "error: failed to allocate guest memory space." << std::endl;
        return 1;
    }

    uint64_t entry_point = 0;
    uint64_t boot_params_gpa = 0;

    if (!kernel_path.empty()) {
        if (!load_linux_kernel(kernel_path, initrd_path, host_ram, ram_size, entry_point, boot_params_gpa)) {
            std::cerr << "error: failed to load linux kernel." << std::endl;
#if defined(_WIN32) || defined(_WIN64)
            VirtualFree(host_ram, 0, MEM_RELEASE);
#else
            munmap(host_ram, ram_size);
#endif
            return 1;
        }
    } else {
        std::cout << "no kernel specified. executing fallback guest test code..." << std::endl;
        std::memcpy(host_ram, GUEST_CODE, sizeof(GUEST_CODE));
        entry_point = 0;
        boot_params_gpa = 0;
    }

    if (!hypervisor->map_guest_memory(0, ram_size, host_ram, 0)) {
        std::cerr << "error: failed to map guest physical memory address range." << std::endl;
#if defined(_WIN32) || defined(_WIN64)
        VirtualFree(host_ram, 0, MEM_RELEASE);
#else
        munmap(host_ram, ram_size);
#endif
        return 1;
    }

    const size_t vram_size = 0x10000000;
    void* host_vram = nullptr;
#if defined(_WIN32) || defined(_WIN64)
    host_vram = VirtualAlloc(nullptr, vram_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
#else
    host_vram = mmap(NULL, vram_size, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
#endif

    if (!host_vram) {
        std::cerr << "error: failed to allocate guest VRAM memory space." << std::endl;
#if defined(_WIN32) || defined(_WIN64)
        VirtualFree(host_ram, 0, MEM_RELEASE);
#else
        munmap(host_ram, ram_size);
#endif
        return 1;
    }

    if (!hypervisor->map_guest_memory(0x40000000, vram_size, host_vram, 1)) {
        std::cerr << "error: failed to map guest VRAM physical address range." << std::endl;
#if defined(_WIN32) || defined(_WIN64)
        VirtualFree(host_vram, 0, MEM_RELEASE);
        VirtualFree(host_ram, 0, MEM_RELEASE);
#else
        munmap(host_vram, vram_size);
        munmap(host_ram, ram_size);
#endif
        return 1;
    }

    if (!hypervisor->setup_vcpu(entry_point, boot_params_gpa)) {
        std::cerr << "error: failed to configure virtual processor." << std::endl;
#if defined(_WIN32) || defined(_WIN64)
        VirtualFree(host_vram, 0, MEM_RELEASE);
        VirtualFree(host_ram, 0, MEM_RELEASE);
#else
        munmap(host_vram, vram_size);
        munmap(host_ram, ram_size);
#endif
        return 1;
    }

    if (!hypervisor->run_loop()) {
        std::cerr << "error: VM execution failed." << std::endl;
    }

#if defined(_WIN32) || defined(_WIN64)
    VirtualFree(host_vram, 0, MEM_RELEASE);
    VirtualFree(host_ram, 0, MEM_RELEASE);
#else
    munmap(host_vram, vram_size);
    munmap(host_ram, ram_size);
#endif
    std::cout << "hyper-x execution completed successfully." << std::endl;
    return 0;
}
