#pragma once
#include "IHypervisor.h"

#include <unordered_map>

class KvmBackend : public IHypervisor {
public:
    KvmBackend() = default;
    ~KvmBackend() override;

    bool initialize() override;
    bool setup_vm() override;
    bool map_guest_memory(uint64_t gpa, size_t size, void* host_addr, uint32_t slot = 0) override;
    bool setup_vcpu(uint64_t rip, uint64_t boot_params_gpa) override;
    bool setup_vcpu_realmode() override;
    bool run_loop() override;

private:
    int kvm_fd_ = -1;
    int vm_fd_ = -1;
    int vcpu_fd_ = -1;
    void* host_ram_ = nullptr;
    size_t ram_size_ = 0;
    void* kvm_run_struct_ = nullptr;
    std::unordered_map<uint64_t, void*> mapped_regions_;
};
