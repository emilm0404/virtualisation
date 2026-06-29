#include "../include/Loader.h"
#include <fstream>
#include <iostream>
#include <cstring>

bool load_linux_kernel(
    const std::string& kernel_path,
    const std::string& initrd_path,
    void* host_ram,
    size_t ram_size,
    uint64_t& entry_point,
    uint64_t& boot_params_gpa
) {
    std::ifstream kf(kernel_path, std::ios::binary);
    if (!kf.is_open()) {
        std::cerr << "loader: failed to open kernel image: " << kernel_path << std::endl;
        return false;
    }

    // read boot sector header to verify signature
    uint8_t boot_sect[1024];
    kf.read(reinterpret_cast<char*>(boot_sect), sizeof(boot_sect));
    if (kf.gcount() < 1024) {
        std::cerr << "loader: kernel file too small." << std::endl;
        return false;
    }

    // verify HdrS signature (offset 0x202)
    uint32_t signature = *reinterpret_cast<uint32_t*>(&boot_sect[0x202]);
    if (signature != 0x53726448) { // "HdrS"
        std::cerr << "loader: invalid kernel signature (not a valid bzImage)." << std::endl;
        return false;
    }

    struct setup_header* original_hdr = reinterpret_cast<struct setup_header*>(&boot_sect[0x1f1]);
    uint8_t setup_sects = original_hdr->setup_sects;
    if (setup_sects == 0) {
        setup_sects = 4;
    }

    size_t setup_code_size = (setup_sects + 1) * 512;
    
    // load protected-mode code to GPA 0x100000 (1MB)
    kf.seekg(setup_code_size, std::ios::beg);
    char* kernel_dest = reinterpret_cast<char*>(host_ram) + 0x100000;
    size_t max_kernel_size = ram_size - 0x100000;
    kf.read(kernel_dest, max_kernel_size);
    size_t kernel_bytes_read = kf.gcount();
    std::cout << "loader: loaded kernel image (" << kernel_bytes_read << " bytes) to GPA 0x100000" << std::endl;

    // load initrd/initramfs if provided to GPA 0x1000000 (16MB)
    uint64_t ramdisk_addr = 0;
    uint64_t ramdisk_size = 0;
    if (!initrd_path.empty()) {
        std::ifstream inf(initrd_path, std::ios::binary);
        if (inf.is_open()) {
            char* initrd_dest = reinterpret_cast<char*>(host_ram) + 0x1000000;
            size_t max_initrd_size = ram_size - 0x1000000;
            inf.read(initrd_dest, max_initrd_size);
            ramdisk_size = inf.gcount();
            ramdisk_addr = 0x1000000;
            std::cout << "loader: loaded initrd (" << ramdisk_size << " bytes) to GPA 0x1000000" << std::endl;
        } else {
            std::cerr << "loader: warning: failed to open initrd image: " << initrd_path << std::endl;
        }
    }

    // write command line to GPA 0x20000 (128KB)
    const std::string cmdline = "console=ttyS0 earlyprintk=serial,ttyS0,115200 quiet panic=-1 root=/dev/ram0 rdinit=/bin/sh";
    char* cmdline_dest = reinterpret_cast<char*>(host_ram) + 0x20000;
    std::memcpy(cmdline_dest, cmdline.c_str(), cmdline.size() + 1);

    // populate boot_params structure at GPA 0x10000 (64KB)
    boot_params_gpa = 0x10000;
    struct boot_params* bp = reinterpret_cast<struct boot_params*>(reinterpret_cast<char*>(host_ram) + boot_params_gpa);
    std::memset(bp, 0, sizeof(*bp));

    // copy setup header from kernel image
    std::memcpy(&bp->hdr, original_hdr, sizeof(bp->hdr));
    
    // configure bootloader params
    bp->hdr.type_of_loader = 0xFF;
    bp->hdr.loadflags |= 0x01; // load high
    bp->hdr.heap_end_ptr = 0xE000;
    bp->hdr.cmd_line_ptr = 0x20000;
    bp->hdr.ramdisk_image = static_cast<uint32_t>(ramdisk_addr);
    bp->hdr.ramdisk_size = static_cast<uint32_t>(ramdisk_size);

    // setup memory map
    bp->e820_entries = 2;
    bp->e820_table[0].addr = 0;
    bp->e820_table[0].size = 0x9F000; // low memory
    bp->e820_table[0].type = 1; // RAM

    bp->e820_table[1].addr = 0x100000;
    bp->e820_table[1].size = ram_size - 0x100000; // high memory
    bp->e820_table[1].type = 1; // RAM

    // setup custom GDT in guest RAM at GPA 0x500
    uint64_t* gdt = reinterpret_cast<uint64_t*>(reinterpret_cast<char*>(host_ram) + 0x500);
    gdt[0] = 0x0000000000000000; // null descriptor
    gdt[1] = 0x00cf9a000000ffff; // code descriptor
    gdt[2] = 0x00cf92000000ffff; // data descriptor

    entry_point = 0x100000;
    return true;
}
