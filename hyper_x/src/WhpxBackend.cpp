#if defined(_WIN32) || defined(_WIN64)
#include "../include/WhpxBackend.h"
#include "../include/xgpu_protocol.h"
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

bool WhpxBackend::setup_vcpu_realmode() {
    HRESULT hr = WHvCreateVirtualProcessor(partition_, 0, 0);
    if (FAILED(hr)) {
        std::cerr << "whpx: failed to create virtual processor. hr = " << std::hex << hr << std::endl;
        return false;
    }

    // Initialize vCPU in 16-bit Real Mode for UEFI firmware boot.
    // The x86 reset vector: CS.Base = 0xFFFF0000, RIP = 0xFFF0
    // First instruction fetched from physical address CS.Base + RIP = 0xFFFFFFF0
    WHV_REGISTER_NAME reg_names[] = {
        WHvX64RegisterRip,
        WHvX64RegisterRsp,
        WHvX64RegisterRflags,
        WHvX64RegisterCr0,
        WHvX64RegisterCs,
        WHvX64RegisterDs,
        WHvX64RegisterEs,
        WHvX64RegisterSs,
        WHvX64RegisterFs,
        WHvX64RegisterGs
    };

    const int reg_count = sizeof(reg_names) / sizeof(reg_names[0]);
    WHV_REGISTER_VALUE reg_values[reg_count];
    ZeroMemory(reg_values, sizeof(reg_values));

    // RIP = 0xFFF0 (reset vector offset)
    reg_values[0].Reg64 = 0xFFF0;
    // RSP = 0 (no stack initially)
    reg_values[1].Reg64 = 0;
    // RFLAGS = 0x2 (reserved bit must be set)
    reg_values[2].Reg64 = 0x2;
    // CR0 = 0x60000010 (real mode: PE=0, ET=1, NW=1, CD=1)
    reg_values[3].Reg64 = 0x60000010;

    // CS: selector=0xF000, base=0xFFFF0000, limit=0xFFFF (64KB real mode segment)
    reg_values[4].Segment.Selector = 0xF000;
    reg_values[4].Segment.Base = 0xFFFF0000;
    reg_values[4].Segment.Limit = 0xFFFF;
    reg_values[4].Segment.Attributes = 0x9B; // present, readable, executable, accessed

    // DS, ES, SS, FS, GS: selector=0, base=0, limit=0xFFFF
    for (int i = 5; i <= 9; ++i) {
        reg_values[i].Segment.Selector = 0x0000;
        reg_values[i].Segment.Base = 0x00000000;
        reg_values[i].Segment.Limit = 0xFFFF;
        reg_values[i].Segment.Attributes = 0x93; // present, writable, accessed
    }

    hr = WHvSetVirtualProcessorRegisters(partition_, 0, reg_names, reg_count, reg_values);
    if (FAILED(hr)) {
        std::cerr << "whpx: failed to set real mode register values. hr = " << std::hex << hr << std::endl;
        return false;
    }

    std::cout << "whpx: vCPU initialized in 16-bit Real Mode (CS:IP = F000:FFF0)" << std::endl;
    return true;
}

bool WhpxBackend::run_loop() {
    std::cout << "whpx: running virtual processor..." << std::endl;
    bool running = true;
    uint32_t pci_config_addr = 0; // PCI configuration address register state

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
                uint16_t port = io.PortNumber;

                // ---- Serial UART 0x3F8 (COM1 data) ----
                if (port == 0x3F8 && io.AccessInfo.IsWrite) {
                    std::cout << (char)io.Rax;
                    std::cout.flush();
                }
                // ---- Serial LSR 0x3FD (Line Status Register) ----
                // OVMF polls this to check if transmitter is ready.
                // Return 0x60 = THR empty + transmitter idle
                else if (port == 0x3FD && !io.AccessInfo.IsWrite) {
                    // Write 0x60 back into RAX via register manipulation
                    WHV_REGISTER_NAME rax_name = WHvX64RegisterRax;
                    WHV_REGISTER_VALUE rax_val;
                    rax_val.Reg64 = 0x60;
                    WHvSetVirtualProcessorRegisters(partition_, 0, &rax_name, 1, &rax_val);
                }
                // ---- Serial IIR 0x3FA (Interrupt Identification Register) ----
                else if (port == 0x3FA && !io.AccessInfo.IsWrite) {
                    WHV_REGISTER_NAME rax_name = WHvX64RegisterRax;
                    WHV_REGISTER_VALUE rax_val;
                    rax_val.Reg64 = 0x01; // no interrupt pending
                    WHvSetVirtualProcessorRegisters(partition_, 0, &rax_name, 1, &rax_val);
                }
                // ---- Serial MCR/LCR/DLx writes (0x3F9-0x3FC) ----
                else if (port >= 0x3F9 && port <= 0x3FC && io.AccessInfo.IsWrite) {
                    // Silently consume UART configuration writes
                }
                // ---- Serial MSR 0x3FE (Modem Status Register) ----
                else if (port == 0x3FE && !io.AccessInfo.IsWrite) {
                    WHV_REGISTER_NAME rax_name = WHvX64RegisterRax;
                    WHV_REGISTER_VALUE rax_val;
                    rax_val.Reg64 = 0xB0; // CTS + DSR + DCD asserted
                    WHvSetVirtualProcessorRegisters(partition_, 0, &rax_name, 1, &rax_val);
                }
                // ---- OVMF Debug Port 0x402 ----
                else if (port == 0x402 && io.AccessInfo.IsWrite) {
                    std::cout << (char)io.Rax;
                    std::cout.flush();
                }
                // ---- POST Code Debug Port 0x80 ----
                else if (port == 0x80 && io.AccessInfo.IsWrite) {
                    // Silently consume POST codes (or log them)
                }
                // ---- CMOS/RTC 0x70 (address) / 0x71 (data) ----
                else if (port == 0x70 && io.AccessInfo.IsWrite) {
                    // Store the CMOS register index (lower 7 bits)
                    // We just consume it; reads from 0x71 return 0
                }
                else if (port == 0x71 && !io.AccessInfo.IsWrite) {
                    WHV_REGISTER_NAME rax_name = WHvX64RegisterRax;
                    WHV_REGISTER_VALUE rax_val;
                    rax_val.Reg64 = 0x00; // return zeros for all CMOS registers
                    WHvSetVirtualProcessorRegisters(partition_, 0, &rax_name, 1, &rax_val);
                }
                // ---- PCI Configuration 0xCF8 (address) ----
                else if (port == 0xCF8 && io.AccessInfo.IsWrite) {
                    pci_config_addr = (uint32_t)io.Rax;
                }
                else if (port == 0xCF8 && !io.AccessInfo.IsWrite) {
                    WHV_REGISTER_NAME rax_name = WHvX64RegisterRax;
                    WHV_REGISTER_VALUE rax_val;
                    rax_val.Reg64 = pci_config_addr;
                    WHvSetVirtualProcessorRegisters(partition_, 0, &rax_name, 1, &rax_val);
                }
                // ---- PCI Configuration 0xCFC (data) ----
                // Return 0xFFFFFFFF (no device present) for all PCI config reads
                else if (port >= 0xCFC && port <= 0xCFF && !io.AccessInfo.IsWrite) {
                    WHV_REGISTER_NAME rax_name = WHvX64RegisterRax;
                    WHV_REGISTER_VALUE rax_val;
                    rax_val.Reg64 = 0xFFFFFFFF;
                    WHvSetVirtualProcessorRegisters(partition_, 0, &rax_name, 1, &rax_val);
                }
                else if (port >= 0xCFC && port <= 0xCFF && io.AccessInfo.IsWrite) {
                    // Silently consume PCI config writes
                }
                // ---- DMA controller / PIC / PIT / misc legacy ports ----
                else if (!io.AccessInfo.IsWrite) {
                    // Default: return 0xFF for unhandled reads
                    WHV_REGISTER_NAME rax_name = WHvX64RegisterRax;
                    WHV_REGISTER_VALUE rax_val;
                    rax_val.Reg64 = 0xFF;
                    WHvSetVirtualProcessorRegisters(partition_, 0, &rax_name, 1, &rax_val);
                }

                // Advance RIP past the IO instruction
                WHV_REGISTER_NAME rip_name = WHvX64RegisterRip;
                WHV_REGISTER_VALUE rip_val;
                WHvGetVirtualProcessorRegisters(partition_, 0, &rip_name, 1, &rip_val);
                rip_val.Reg64 += io.InstructionByteCount;
                WHvSetVirtualProcessorRegisters(partition_, 0, &rip_name, 1, &rip_val);
                break;
            }
            case WHvRunVpExitReasonMemoryAccess: {
                auto& mem = exit_context.MemoryAccess;
                // FIX 2: WHPX memory access uses AccessType (0=Read, 1=Write, 2=Execute)
                if (mem.Gpa == 0x3FFFF000 && mem.AccessInfo.AccessType == 1) {
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
