#pragma once
#include <cstdint>
#include <string>

class IHypervisor {
public:
    virtual ~IHypervisor() = default;

    virtual bool initialize() = 0;
    virtual bool setup_vm() = 0;
    virtual bool map_guest_memory(uint64_t gpa, size_t size, void* host_addr) = 0;
    virtual bool setup_vcpu(uint64_t rip) = 0;
    virtual bool run_loop() = 0;
};
