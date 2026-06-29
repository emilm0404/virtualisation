#pragma once
#include "IHypervisor.h"

#if defined(_WIN32) || defined(_WIN64)
#include <windows.h>
#include <winhvplatform.h>

#include <unordered_map>

class WhpxBackend : public IHypervisor {
public:
    WhpxBackend() = default;
    ~WhpxBackend() override;

    bool initialize() override;
    bool setup_vm() override;
    bool map_guest_memory(uint64_t gpa, size_t size, void* host_addr, uint32_t slot = 0) override;
    bool setup_vcpu(uint64_t rip, uint64_t boot_params_gpa) override;
    bool run_loop() override;

private:
    WHV_PARTITION_HANDLE partition_ = nullptr;
    void* host_ram_ = nullptr;
    size_t ram_size_ = 0;
    std::unordered_map<uint64_t, void*> mapped_regions_;
};
#endif
