#include "../include/KvmBackend.h"
#include <iostream>

#ifdef __linux__
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <linux/kvm.h>

KvmBackend::~KvmBackend() {
    if (kvm_run_struct_) {
        munmap(kvm_run_struct_, ioctl(kvm_fd_, KVM_GET_VCPU_MMAP_SIZE, 0));
    }
    if (vcpu_fd_ >= 0) close(vcpu_fd_);
    if (vm_fd_ >= 0) close(vm_fd_);
    if (kvm_fd_ >= 0) close(kvm_fd_);
}

bool KvmBackend::initialize() {
    kvm_fd_ = open("/dev/kvm", O_RDWR | O_CLOEXEC);
    if (kvm_fd_ < 0) {
        std::cerr << "kvm: failed to open /dev/kvm." << std::endl;
        return false;
    }
    int version = ioctl(kvm_fd_, KVM_GET_API_VERSION, 0);
    if (version != 12) {
        std::cerr << "kvm: unsupported api version " << version << std::endl;
        return false;
    }
    return true;
}

bool KvmBackend::setup_vm() {
    vm_fd_ = ioctl(kvm_fd_, KVM_CREATE_VM, 0);
    if (vm_fd_ < 0) {
        std::cerr << "kvm: failed to create VM." << std::endl;
        return false;
    }

    // create in-kernel interrupt controller (APIC)
    if (ioctl(vm_fd_, KVM_CREATE_IRQCHIP, 0) < 0) {
        std::cerr << "kvm: failed to create in-kernel IRQCHIP." << std::endl;
    }

    return true;
}

bool KvmBackend::map_guest_memory(uint64_t gpa, size_t size, void* host_addr, uint32_t slot) {
    struct kvm_userspace_memory_region region = {};
    region.slot = slot;
    region.guest_phys_addr = gpa;
    region.memory_size = size;
    region.userspace_addr = (uint64_t)host_addr;

    if (ioctl(vm_fd_, KVM_SET_USER_MEMORY_REGION, &region) < 0) {
        std::cerr << "kvm: failed to set memory region." << std::endl;
        return false;
    }
    host_ram_ = host_addr;
    ram_size_ = size;
    mapped_regions_[gpa] = host_addr;
    return true;
}

bool KvmBackend::setup_vcpu(uint64_t rip, uint64_t boot_params_gpa) {
    vcpu_fd_ = ioctl(vm_fd_, KVM_CREATE_VCPU, 0);
    if (vcpu_fd_ < 0) {
        std::cerr << "kvm: failed to create VCPU." << std::endl;
        return false;
    }

    int mmap_size = ioctl(kvm_fd_, KVM_GET_VCPU_MMAP_SIZE, 0);
    if (mmap_size < 0) {
        std::cerr << "kvm: failed to get VCPU mmap size." << std::endl;
        return false;
    }

    kvm_run_struct_ = mmap(NULL, mmap_size, PROT_READ | PROT_WRITE, MAP_SHARED, vcpu_fd_, 0);
    if (kvm_run_struct_ == MAP_FAILED) {
        std::cerr << "kvm: mmap vcpu struct failed." << std::endl;
        return false;
    }

    struct kvm_sregs sregs;
    if (ioctl(vcpu_fd_, KVM_GET_SREGS, &sregs) < 0) return false;

    sregs.gdt.base = 0x500;
    sregs.gdt.limit = 23;

    sregs.cs.selector = 0x8;
    sregs.cs.base = 0;
    sregs.cs.limit = 0xFFFFFFFF;
    sregs.cs.g = 1;
    sregs.cs.db = 1;
    sregs.cs.present = 1;
    sregs.cs.s = 1;
    sregs.cs.type = 11;

    struct kvm_segment ds_seg = {};
    ds_seg.selector = 0x10;
    ds_seg.base = 0;
    ds_seg.limit = 0xFFFFFFFF;
    ds_seg.g = 1;
    ds_seg.db = 1;
    ds_seg.present = 1;
    ds_seg.s = 1;
    ds_seg.type = 3;

    sregs.ds = ds_seg;
    sregs.es = ds_seg;
    sregs.ss = ds_seg;
    sregs.fs = ds_seg;
    sregs.gs = ds_seg;

    sregs.cr0 = 0x1;

    if (ioctl(vcpu_fd_, KVM_SET_SREGS, &sregs) < 0) return false;

    struct kvm_regs regs = {};
    regs.rip = rip;
    regs.rsi = boot_params_gpa;
    regs.rsp = 0x8000;
    regs.rflags = 2;

    if (ioctl(vcpu_fd_, KVM_SET_REGS, &regs) < 0) return false;

    return true;
}

bool KvmBackend::run_loop() {
    std::cout << "kvm: running virtual processor..." << std::endl;
    struct kvm_run* run = (struct kvm_run*)kvm_run_struct_;
    bool running = true;
    while (running) {
        if (ioctl(vcpu_fd_, KVM_RUN, 0) < 0) {
            std::cerr << "kvm: run failed." << std::endl;
            return false;
        }

        switch (run->exit_reason) {
            case KVM_EXIT_IO: {
                if (run->io.port == 0x3F8 && run->io.direction == KVM_EXIT_IO_OUT) {
                    char* data = (char*)run + run->io.data_offset;
                    for (int i = 0; i < run->io.count; ++i) {
                        std::cout << *data;
                        data += run->io.size;
                    }
                    std::cout.flush();
                } else if (run->io.port == 0x80 && run->io.direction == KVM_EXIT_IO_OUT) {
                    char* data = (char*)run + run->io.data_offset;
                    std::cout << "[guest output] port 0x80: " << std::hex << (int)*data << std::endl;
                }
                break;
            }
            case KVM_EXIT_MMIO: {
                if (run->mmio.phys_addr == 0x3FFFF000 && run->mmio.is_write) {
                    void* host_vram = mapped_regions_[0x40000000];
                    if (host_vram) {
                        uint32_t* cmd_buf = (uint32_t*)host_vram;
                        std::cout << "[host x-gpu] doorbell rung! command buffer head: 0x" 
                                  << std::hex << *cmd_buf << std::dec << std::endl;
                        if (*cmd_buf == 0xFF0000) {
                            std::cout << "[host x-gpu renderer] received framebuffer trigger! rendering red frame (color 0xFF0000)!" << std::endl;
                        }
                    }
                }
                break;
            }
            case KVM_EXIT_HLT:
                std::cout << "\n[guest halt] HLT execution exit." << std::endl;
                running = false;
                break;
            default:
                std::cout << "\nkvm: unhandled exit reason: " << run->exit_reason << std::endl;
                running = false;
                break;
        }
    }
    return true;
}

#else

KvmBackend::~KvmBackend() {}
bool KvmBackend::initialize() {
    std::cerr << "kvm: KVM backend only supported on Linux." << std::endl;
    return false;
}
bool KvmBackend::setup_vm() { return false; }
bool KvmBackend::map_guest_memory(uint64_t gpa, size_t size, void* host_addr, uint32_t slot) { return false; }
bool KvmBackend::setup_vcpu(uint64_t rip, uint64_t boot_params_gpa) { return false; }
bool KvmBackend::run_loop() { return false; }

#endif
