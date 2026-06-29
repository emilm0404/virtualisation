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

const unsigned char GUEST_CODE[] = {
    0xB0, 0x64,
    0xE6, 0x80,
    0xF4
};

int main() {
    std::cout << "hyper-x starting execution..." << std::endl;

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

    const size_t ram_size = 0x10000;
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

    std::memcpy(host_ram, GUEST_CODE, sizeof(GUEST_CODE));

    if (!hypervisor->map_guest_memory(0, ram_size, host_ram)) {
        std::cerr << "error: failed to map guest physical memory address range." << std::endl;
#if defined(_WIN32) || defined(_WIN64)
        VirtualFree(host_ram, 0, MEM_RELEASE);
#else
        munmap(host_ram, ram_size);
#endif
        return 1;
    }

    if (!hypervisor->setup_vcpu(0)) {
        std::cerr << "error: failed to configure virtual processor." << std::endl;
#if defined(_WIN32) || defined(_WIN64)
        VirtualFree(host_ram, 0, MEM_RELEASE);
#else
        munmap(host_ram, ram_size);
#endif
        return 1;
    }

    if (!hypervisor->run_loop()) {
        std::cerr << "error: VM execution failed." << std::endl;
    }

#if defined(_WIN32) || defined(_WIN64)
    VirtualFree(host_ram, 0, MEM_RELEASE);
#else
    munmap(host_ram, ram_size);
#endif
    std::cout << "hyper-x execution completed successfully." << std::endl;
    return 0;
}
