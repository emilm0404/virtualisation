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
    return true;
}

bool KvmBackend::map_guest_memory(uint64_t gpa, size_t size, void* host_addr) {
    struct kvm_userspace_memory_region region = {};
    region.slot = 0;
    region.guest_phys_addr = gpa;
    region.memory_size = size;
    region.userspace_addr = (uint64_t)host_addr;

    if (ioctl(vm_fd_, KVM_SET_USER_MEMORY_REGION, &region) < 0) {
        std::cerr << "kvm: failed to set memory region." << std::endl;
        return false;
    }
    host_ram_ = host_addr;
    ram_size_ = size;
    return true;
}

bool KvmBackend::setup_vcpu(uint64_t rip) {
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
    sregs.cs.base = 0;
    sregs.cs.selector = 0;
    if (ioctl(vcpu_fd_, KVM_SET_SREGS, &sregs) < 0) return false;

    struct kvm_regs regs = {};
    regs.rip = rip;
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
                if (run->io.port == 0x80 && run->io.direction == KVM_EXIT_IO_OUT) {
                    char* data = (char*)run + run->io.data_offset;
                    std::cout << "[guest output] port 0x80: " << std::hex << (int)*data << std::endl;
                }
                break;
            }
            case KVM_EXIT_HLT:
                std::cout << "[guest halt] HLT execution exit." << std::endl;
                running = false;
                break;
            default:
                std::cout << "kvm: unhandled exit reason: " << run->exit_reason << std::endl;
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
bool KvmBackend::map_guest_memory(uint64_t gpa, size_t size, void* host_addr) { return false; }
bool KvmBackend::setup_vcpu(uint64_t rip) { return false; }
bool KvmBackend::run_loop() { return false; }

#endif
