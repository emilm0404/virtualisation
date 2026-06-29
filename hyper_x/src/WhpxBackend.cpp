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

    hr = WHvSetupPartition(partition_);
    if (FAILED(hr)) {
        std::cerr << "whpx: failed to setup partition. hr = " << std::hex << hr << std::endl;
        return false;
    }

    return true;
}

bool WhpxBackend::map_guest_memory(uint64_t gpa, size_t size, void* host_addr) {
    HRESULT hr = WHvMapGpaRange(partition_, host_addr, gpa, size, 
                                WHvMapGpaRangeFlagRead | WHvMapGpaRangeFlagWrite | WHvMapGpaRangeFlagExecute);
    if (FAILED(hr)) {
        std::cerr << "whpx: failed to map GPA range. hr = " << std::hex << hr << std::endl;
        return false;
    }
    host_ram_ = host_addr;
    ram_size_ = size;
    return true;
}

bool WhpxBackend::setup_vcpu(uint64_t rip) {
    HRESULT hr = WHvCreateVirtualProcessor(partition_, 0, 0);
    if (FAILED(hr)) {
        std::cerr << "whpx: failed to create virtual processor. hr = " << std::hex << hr << std::endl;
        return false;
    }

    WHV_REGISTER_NAME reg_names[] = {
        WHvX64RegisterRip,
        WHvX64RegisterCs
    };
    WHV_REGISTER_VALUE reg_values[2];
    ZeroMemory(&reg_values, sizeof(reg_values));
    reg_values[0].Reg64 = rip;
    reg_values[1].Segment.Selector = 0;
    reg_values[1].Segment.Base = 0;
    reg_values[1].Segment.Limit = 0xFFFF;
    reg_values[1].Segment.Attributes = 0x9B; // exec/read code segment

    hr = WHvSetVirtualProcessorRegisters(partition_, 0, reg_names, 2, reg_values);
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
                if (io.Port == 0x80 && io.AccessInfo.IsWrite) {
                    std::cout << "[guest output] port 0x80: " << std::hex << (int)io.Rax << std::endl;
                }
                
                // advance rip over out instruction
                WHV_REGISTER_NAME rip_name = WHvX64RegisterRip;
                WHV_REGISTER_VALUE rip_val;
                WHvGetVirtualProcessorRegisters(partition_, 0, &rip_name, 1, &rip_val);
                rip_val.Reg64 += io.InstructionByteCount;
                WHvSetVirtualProcessorRegisters(partition_, 0, &rip_name, 1, &rip_val);
                break;
            }
            case WHvRunVpExitReasonX64Halt:
                std::cout << "[guest halt] HLT execution exit." << std::endl;
                running = false;
                break;
            default:
                std::cout << "whpx: unhandled exit reason: " << exit_context.ExitReason << std::endl;
                running = false;
                break;
        }
    }
    return true;
}
#endif
