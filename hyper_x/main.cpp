#include <windows.h>
#include <winhvplatform.h>
#include <iostream>
#include <vector>

#pragma comment(lib, "WinHvPlatform.lib")

// simple guest program:
// mov al, 42   -> B0 2A
// out 0x80, al -> E6 80
// hlt          -> F4
const unsigned char GUEST_CODE[] = {
    0xB0, 0x2A,
    0xE6, 0x80,
    0xF4
};

int main() {
    std::cout << "starting hyper-x scratch hypervisor utilizing windows hypervisor platform (whp)..." << std::endl;

    // check if the hypervisor is present on host.
    WHV_CAPABILITY capability;
    HRESULT hr = WHvGetCapability(WHvCapabilityCodeHypervisorPresent, &capability, sizeof(capability), nullptr);
    if (FAILED(hr) || !capability.HypervisorPresent) {
        std::cerr << "error: windows hypervisor platform is not enabled on this host." << std::endl;
        return 1;
    }

    // create partition
    WHV_PARTITION_HANDLE partition = nullptr;
    hr = WHvCreatePartition(&partition);
    if (FAILED(hr)) {
        std::cerr << "error: failed to create hypervisor partition. hr = " << std::hex << hr << std::endl;
        return 1;
    }

    // configure virtual processor count (1 vCPU)
    WHV_PARTITION_PROPERTY prop;
    ZeroMemory(&prop, sizeof(prop));
    prop.ProcessorCount = 1;
    hr = WHvSetPartitionProperty(partition, WHvPartitionPropertyCodeProcessorCount, &prop, sizeof(prop));
    if (FAILED(hr)) {
        std::cerr << "error: failed to set processor count. hr = " << std::hex << hr << std::endl;
        WHvDeletePartition(partition);
        return 1;
    }

    // setup partition
    hr = WHvSetupPartition(partition);
    if (FAILED(hr)) {
        std::cerr << "error: failed to setup partition. hr = " << std::hex << hr << std::endl;
        WHvDeletePartition(partition);
        return 1;
    }

    // allocate guest memory (1 page = 4KB)
    const UINT64 guest_ram_size = 0x1000;
    void* guest_ram = VirtualAlloc(nullptr, guest_ram_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!guest_ram) {
        std::cerr << "error: failed to allocate guest physical memory." << std::endl;
        WHvDeletePartition(partition);
        return 1;
    }

    // copy guest program to guest RAM
    CopyMemory(guest_ram, GUEST_CODE, sizeof(GUEST_CODE));

    // map memory into the partition
    WHV_GUEST_PHYSICAL_ADDRESS gpa = 0;
    hr = WHvMapGpaRange(partition, guest_ram, gpa, guest_ram_size, WHvMapGpaRangeFlagRead | WHvMapGpaRangeFlagWrite | WHvMapGpaRangeFlagExecute);
    if (FAILED(hr)) {
        std::cerr << "error: failed to map GPA range. hr = " << std::hex << hr << std::endl;
        VirtualFree(guest_ram, 0, MEM_RELEASE);
        WHvDeletePartition(partition);
        return 1;
    }

    // create virtual processor
    hr = WHvCreateVirtualProcessor(partition, 0, 0);
    if (FAILED(hr)) {
        std::cerr << "error: failed to create virtual processor. hr = " << std::hex << hr << std::endl;
        WHvUnmapGpaRange(partition, gpa, guest_ram_size);
        VirtualFree(guest_ram, 0, MEM_RELEASE);
        WHvDeletePartition(partition);
        return 1;
    }

    // configure initial registers (setup instruction pointer CS and IP)
    WHV_REGISTER_NAME reg_names[] = {
        WHvX64RegisterRip,
        WHvX64RegisterCs
    };
    WHV_REGISTER_VALUE reg_values[2];
    ZeroMemory(&reg_values, sizeof(reg_values));
    reg_values[0].Reg64 = 0; // RIP points to start of guest RAM (GPA 0)
    reg_values[1].Segment.Selector = 0;
    reg_values[1].Segment.Base = 0;
    reg_values[1].Segment.Limit = 0xFFFF;
    reg_values[1].Segment.Attributes = 0x9B; // execute/read code segment

    hr = WHvSetVirtualProcessorRegisters(partition, 0, reg_names, 2, reg_values);
    if (FAILED(hr)) {
        std::cerr << "error: failed to set registers. hr = " << std::hex << hr << std::endl;
        WHvDeleteVirtualProcessor(partition, 0);
        WHvUnmapGpaRange(partition, gpa, guest_ram_size);
        VirtualFree(guest_ram, 0, MEM_RELEASE);
        WHvDeletePartition(partition);
        return 1;
    }

    // run virtual processor loop
    std::cout << "entering guest execution loop..." << std::endl;
    bool running = true;
    while (running) {
        WHV_RUN_VP_EXIT_CONTEXT exit_context;
        hr = WHvRunVirtualProcessor(partition, 0, &exit_context, sizeof(exit_context));
        if (FAILED(hr)) {
            std::cerr << "error: failed to run virtual processor. hr = " << std::hex << hr << std::endl;
            break;
        }

        switch (exit_context.ExitReason) {
            case WHvRunVpExitReasonX64IoPortAccess: {
                auto& io = exit_context.IoPortAccess;
                if (io.Port == 0x80 && io.AccessInfo.IsWrite) {
                    std::cout << "[guest output] wrote value to port 0x80: " << std::hex << (int)io.Rax << std::endl;
                }
                // advance rip over the out instruction (2 bytes)
                WHV_REGISTER_NAME rip_name = WHvX64RegisterRip;
                WHV_REGISTER_VALUE rip_val;
                WHvGetVirtualProcessorRegisters(partition, 0, &rip_name, 1, &rip_val);
                rip_val.Reg64 += io.InstructionByteCount;
                WHvSetVirtualProcessorRegisters(partition, 0, &rip_name, 1, &rip_val);
                break;
            }
            case WHvRunVpExitReasonX64Halt:
                std::cout << "[guest halt] virtual processor executed HLT. shutting down." << std::endl;
                running = false;
                break;
            default:
                std::cout << "unhandled exit reason: " << exit_context.ExitReason << std::endl;
                running = false;
                break;
        }
    }

    // cleanup
    WHvDeleteVirtualProcessor(partition, 0);
    WHvUnmapGpaRange(partition, gpa, guest_ram_size);
    VirtualFree(guest_ram, 0, MEM_RELEASE);
    WHvDeletePartition(partition);
    std::cout << "hypervisor shutdown complete." << std::endl;
    return 0;
}
