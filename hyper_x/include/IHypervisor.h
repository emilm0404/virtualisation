#pragma once
#include <cstdint>
#include <string>

class IHypervisor {
public:
    virtual ~IHypervisor() = default;

    virtual bool initialize() = 0;
    virtual bool setup_vm() = 0;
    virtual bool map_guest_memory(uint64_t gpa, size_t size, void* host_addr, uint32_t slot = 0) = 0;
    virtual bool setup_vcpu(uint64_t rip, uint64_t boot_params_gpa) = 0;
    virtual bool run_loop() = 0;
};
