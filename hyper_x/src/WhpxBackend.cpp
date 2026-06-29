#if defined(_WIN32) || defined(_WIN64)
#include "../include/WhpxBackend.h"
#include <iostream>

WhpxBackend::~WhpxBackend() {
    if (partition_) {
        WHvDeleteVirtualProcessor(partition_, 0);
        if (host_ram_ && ram_size_ > 0) {
            WHvUnmapGpaRange(partition_, 0, ram_size_);
        }
        WHvDeletePartition(partition_);
    }
}

bool WhpxBackend::initialize() {
    WHV_CAPABILITY capability;
    HRESULT hr = WHvGetCapability(WHvCapabilityCodeHypervisorPresent, &capability, sizeof(capability), nullptr);
    if (FAILED(hr) || !capability.HypervisorPresent) {
        std::cerr << "whpx: hypervisor not present on host." << std::endl;
        return false;
    }
    return true;
}

bool WhpxBackend::setup_vm() {
    HRESULT hr = WHvCreatePartition(&partition_);
    if (FAILED(hr)) {
        std::cerr << "whpx: failed to create partition. hr = " << std::hex << hr << std::endl;
        return false;
    }

    WHV_PARTITION_PROPERTY prop;
    ZeroMemory(&prop, sizeof(prop));
    prop.ProcessorCount = 1;
    hr = WHvSetPartitionProperty(partition_, WHvPartitionPropertyCodeProcessorCount, &prop, sizeof(prop));
    if (FAILED(hr)) {
        std::cerr << "whpx: failed to set processor count. hr = " << std::hex << hr << std::endl;
        return false;
    }

    // enable local apic emulation mode
    WHV_PARTITION_PROPERTY prop_apic;
    ZeroMemory(&prop_apic, sizeof(prop_apic));
    prop_apic.LocalApicEmulationMode = WHvX64LocalApicEmulationModeXApic;
    hr = WHvSetPartitionProperty(partition_, WHvPartitionPropertyCodeLocalApicEmulationMode, &prop_apic, sizeof(prop_apic));
    if (FAILED(hr)) {
        std::cerr << "whpx: failed to enable Local APIC emulation. hr = " << std::hex << hr << std::endl;
    }

    hr = WHvSetupPartition(partition_);
    if (FAILED(hr)) {
        std::cerr << "whpx: failed to setup partition. hr = " << std::hex << hr << std::endl;
        return false;
    }

    return true;
}

bool WhpxBackend::map_guest_memory(uint64_t gpa, size_t size, void* host_addr, uint32_t slot) {
    HRESULT hr = WHvMapGpaRange(partition_, host_addr, gpa, size, 
                                WHvMapGpaRangeFlagRead | WHvMapGpaRangeFlagWrite | WHvMapGpaRangeFlagExecute);
    if (FAILED(hr)) {
        std::cerr << "whpx: failed to map GPA range. hr = " << std::hex << hr << std::endl;
        return false;
    }
    host_ram_ = host_addr;
    ram_size_ = size;
    mapped_regions_[gpa] = host_addr;
    return true;
}

bool WhpxBackend::setup_vcpu(uint64_t rip, uint64_t boot_params_gpa) {
    HRESULT hr = WHvCreateVirtualProcessor(partition_, 0, 0);
    if (FAILED(hr)) {
        std::cerr << "whpx: failed to create virtual processor. hr = " << std::hex << hr << std::endl;
        return false;
    }

    // setup 32-bit protected mode registers
    WHV_REGISTER_NAME reg_names[] = {
        WHvX64RegisterRip,
        WHvX64RegisterRsi,
        WHvX64RegisterRsp,
        WHvX64RegisterGdtr,
        WHvX64RegisterCs,
        WHvX64RegisterDs,
        WHvX64RegisterEs,
        WHvX64RegisterSs,
        WHvX64RegisterFs,
        WHvX64RegisterGs,
        WHvX64RegisterCr0
    };

    const int reg_count = sizeof(reg_names) / sizeof(reg_names[0]);
    WHV_REGISTER_VALUE reg_values[reg_count];
    ZeroMemory(reg_values, sizeof(reg_values));

    reg_values[0].Reg64 = rip;
    reg_values[1].Reg64 = boot_params_gpa;
    reg_values[2].Reg64 = 0x8000;

    reg_values[3].Table.Base = 0x500;
    reg_values[3].Table.Limit = 23;

    reg_values[4].Segment.Selector = 0x8;
    reg_values[4].Segment.Base = 0;
    reg_values[4].Segment.Limit = 0xFFFFFFFF;
    reg_values[4].Segment.Attributes = 0xC9B;

    for (int i = 5; i <= 9; ++i) {
        reg_values[i].Segment.Selector = 0x10;
        reg_values[i].Segment.Base = 0;
        reg_values[i].Segment.Limit = 0xFFFFFFFF;
        reg_values[i].Segment.Attributes = 0xC93;
    }

    reg_values[10].Reg64 = 0x1;

    hr = WHvSetVirtualProcessorRegisters(partition_, 0, reg_names, reg_count, reg_values);
    if (FAILED(hr)) {
        std::cerr << "whpx: failed to set register values. hr = " << std::hex << hr << std::endl;
        return false;
    }

    return true;
}

bool WhpxBackend::run_loop() {
    std::cout << "whpx: running virtual processor..." << std::endl;
    bool running = true;
    while (running) {
        WHV_RUN_VP_EXIT_CONTEXT exit_context;
        HRESULT hr = WHvRunVirtualProcessor(partition_, 0, &exit_context, sizeof(exit_context));
        if (FAILED(hr)) {
            std::cerr << "whpx: run execution error. hr = " << std::hex << hr << std::endl;
            return false;
        }

        switch (exit_context.ExitReason) {
            case WHvRunVpExitReasonX64IoPortAccess: {
                auto& io = exit_context.IoPortAccess;
                if (io.Port == 0x3F8 && io.AccessInfo.IsWrite) {
                    std::cout << (char)io.Rax;
                    std::cout.flush();
                } else if (io.Port == 0x80 && io.AccessInfo.IsWrite) {
                    std::cout << "[guest output] port 0x80: " << std::hex << (int)io.Rax << std::endl;
                }
                
                WHV_REGISTER_NAME rip_name = WHvX64RegisterRip;
                WHV_REGISTER_VALUE rip_val;
                WHvGetVirtualProcessorRegisters(partition_, 0, &rip_name, 1, &rip_val);
                rip_val.Reg64 += io.InstructionByteCount;
                WHvSetVirtualProcessorRegisters(partition_, 0, &rip_name, 1, &rip_val);
                break;
            }
            case WHvRunVpExitReasonMemoryAccess: {
                auto& mem = exit_context.MemoryAccess;
                if (mem.Gpa == 0x3FFFF000 && mem.AccessInfo.IsWrite) {
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
                
                WHV_REGISTER_NAME rip_name = WHvX64RegisterRip;
                WHV_REGISTER_VALUE rip_val;
                WHvGetVirtualProcessorRegisters(partition_, 0, &rip_name, 1, &rip_val);
                if (mem.InstructionByteCount > 0) {
                    rip_val.Reg64 += mem.InstructionByteCount;
                } else {
                    rip_val.Reg64 += 3; // basic default instruction advance step
                }
                WHvSetVirtualProcessorRegisters(partition_, 0, &rip_name, 1, &rip_val);
                break;
            }
            case WHvRunVpExitReasonX64Halt:
                std::cout << "\n[guest halt] HLT execution exit." << std::endl;
                running = false;
                break;
            default:
                std::cout << "\nwhpx: unhandled exit reason: " << exit_context.ExitReason << std::endl;
                running = false;
                break;
        }
    }
    return true;
}
#endif
