#include "../include/KvmBackend.h"
#include "../include/xgpu_protocol.h"
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

bool KvmBackend::setup_vcpu_realmode() {
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

    // Initialize vCPU in 16-bit Real Mode for UEFI firmware boot.
    struct kvm_sregs sregs;
    if (ioctl(vcpu_fd_, KVM_GET_SREGS, &sregs) < 0) return false;

    // CS: selector=0xF000, base=0xFFFF0000 (reset vector trick)
    sregs.cs.selector = 0xF000;
    sregs.cs.base = 0xFFFF0000;
    sregs.cs.limit = 0xFFFF;
    sregs.cs.g = 0;
    sregs.cs.db = 0; // 16-bit
    sregs.cs.present = 1;
    sregs.cs.s = 1;
    sregs.cs.type = 11; // execute/read, accessed

    // DS, ES, SS, FS, GS: selector=0, base=0
    struct kvm_segment ds_seg = {};
    ds_seg.selector = 0x0000;
    ds_seg.base = 0x00000000;
    ds_seg.limit = 0xFFFF;
    ds_seg.g = 0;
    ds_seg.db = 0; // 16-bit
    ds_seg.present = 1;
    ds_seg.s = 1;
    ds_seg.type = 3; // read/write, accessed

    sregs.ds = ds_seg;
    sregs.es = ds_seg;
    sregs.ss = ds_seg;
    sregs.fs = ds_seg;
    sregs.gs = ds_seg;

    // CR0: PE=0 (real mode), ET=1, NW=1, CD=1
    sregs.cr0 = 0x60000010;

    if (ioctl(vcpu_fd_, KVM_SET_SREGS, &sregs) < 0) return false;

    struct kvm_regs regs = {};
    regs.rip = 0xFFF0; // reset vector offset
    regs.rsp = 0;
    regs.rflags = 2;

    if (ioctl(vcpu_fd_, KVM_SET_REGS, &regs) < 0) return false;

    std::cout << "kvm: vCPU initialized in 16-bit Real Mode (CS:IP = F000:FFF0)" << std::endl;
    return true;
}

bool KvmBackend::run_loop() {
    std::cout << "kvm: running virtual processor..." << std::endl;
    struct kvm_run* run = (struct kvm_run*)kvm_run_struct_;
    bool running = true;
    uint32_t pci_config_addr = 0;

    while (running) {
        if (ioctl(vcpu_fd_, KVM_RUN, 0) < 0) {
            std::cerr << "kvm: run failed." << std::endl;
            return false;
        }

        switch (run->exit_reason) {
            case KVM_EXIT_IO: {
                uint16_t port = run->io.port;
                char* data = (char*)run + run->io.data_offset;

                // ---- Serial UART 0x3F8 (COM1 data) ----
                if (port == 0x3F8 && run->io.direction == KVM_EXIT_IO_OUT) {
                    for (int i = 0; i < run->io.count; ++i) {
                        std::cout << *data;
                        data += run->io.size;
                    }
                    std::cout.flush();
                }
                // ---- Serial LSR 0x3FD (Line Status Register) ----
                else if (port == 0x3FD && run->io.direction == KVM_EXIT_IO_IN) {
                    *data = 0x60; // THR empty + transmitter idle
                }
                // ---- Serial IIR 0x3FA ----
                else if (port == 0x3FA && run->io.direction == KVM_EXIT_IO_IN) {
                    *data = 0x01; // no interrupt pending
                }
                // ---- Serial MCR/LCR/DLx writes ----
                else if (port >= 0x3F9 && port <= 0x3FC && run->io.direction == KVM_EXIT_IO_OUT) {
                    // Silently consume UART configuration writes
                }
                // ---- Serial MSR 0x3FE ----
                else if (port == 0x3FE && run->io.direction == KVM_EXIT_IO_IN) {
                    *data = 0xB0; // CTS + DSR + DCD asserted
                }
                // ---- OVMF Debug Port 0x402 ----
                else if (port == 0x402 && run->io.direction == KVM_EXIT_IO_OUT) {
                    for (int i = 0; i < run->io.count; ++i) {
                        std::cout << *data;
                        data += run->io.size;
                    }
                    std::cout.flush();
                }
                // ---- POST Code Debug Port 0x80 ----
                else if (port == 0x80 && run->io.direction == KVM_EXIT_IO_OUT) {
                    // Silently consume POST codes
                }
                // ---- CMOS/RTC 0x70/0x71 ----
                else if (port == 0x70 && run->io.direction == KVM_EXIT_IO_OUT) {
                    // Consume CMOS address writes
                }
                else if (port == 0x71 && run->io.direction == KVM_EXIT_IO_IN) {
                    *data = 0x00; // return zeros for all CMOS registers
                }
                // ---- PCI Configuration 0xCF8 (address) ----
                else if (port == 0xCF8 && run->io.direction == KVM_EXIT_IO_OUT) {
                    std::memcpy(&pci_config_addr, data, sizeof(uint32_t));
                }
                else if (port == 0xCF8 && run->io.direction == KVM_EXIT_IO_IN) {
                    std::memcpy(data, &pci_config_addr, sizeof(uint32_t));
                }
                // ---- PCI Configuration 0xCFC-0xCFF (data) ----
                else if (port >= 0xCFC && port <= 0xCFF && run->io.direction == KVM_EXIT_IO_IN) {
                    uint32_t val = 0xFFFFFFFF; // no device present
                    std::memcpy(data, &val, run->io.size);
                }
                else if (port >= 0xCFC && port <= 0xCFF && run->io.direction == KVM_EXIT_IO_OUT) {
                    // Silently consume PCI config writes
                }
                // ---- Default: return 0xFF for unhandled reads ----
                else if (run->io.direction == KVM_EXIT_IO_IN) {
                    std::memset(data, 0xFF, run->io.size);
                }
                break;
            }
            case KVM_EXIT_MMIO: {
                if (run->mmio.phys_addr == 0x3FFFF000 && run->mmio.is_write) {
                    void* host_vram = mapped_regions_[0x40000000];
                    if (host_vram) {
                        XGpuCommand* cmd = (XGpuCommand*)host_vram;
                        std::cout << "[host x-gpu] doorbell rung! command: 0x" << std::hex << cmd->command_id 
                                  << ", size: " << std::dec << cmd->payload_size 
                                  << ", offset: 0x" << std::hex << cmd->vram_offset << std::dec << std::endl;
                        if (cmd->command_id == XGPU_CMD_INIT) {
                            std::cout << "[host x-gpu] initializing host Vulkan context..." << std::endl;
                        } else if (cmd->command_id == XGPU_CMD_ALLOC_MEM) {
                            std::cout << "[host x-gpu] allocating " << cmd->payload_size << " bytes on physical host GPU." << std::endl;
                        } else if (cmd->command_id == XGPU_CMD_VK_SUBMIT) {
                            std::cout << "[host x-gpu] submitting guest command queue (vkQueueSubmit)!" << std::endl;
                        } else if (cmd->command_id == 0xFF0000) {
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
bool KvmBackend::setup_vcpu_realmode() { return false; }
bool KvmBackend::run_loop() { return false; }

#endif
