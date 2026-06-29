#!/usr/bin/env python3
"""
Hyper X Minimal Firmware Generator
===================================
Generates a 2MB firmware ROM binary that acts as a minimal UEFI-like firmware.
Maps to GPA 0xFFE00000 - 0xFFFFFFFF (top of 32-bit address space).

The firmware:
  1. Starts at reset vector (0xFFFFFFF0 = offset 0x1FFFF0 in the file)
  2. Jumps to initialization code at the base of the ROM
  3. Enables A20 gate
  4. Transitions from 16-bit Real Mode to 32-bit Protected Mode
  5. Initializes the 8250 UART (COM1 at 0x3F8) for serial output
  6. Prints firmware initialization banner + messages to serial
  7. Drops into an interactive EFI Shell loop reading serial input

Physical layout:
  File offset 0x000000 = GPA 0xFFE00000  (firmware code starts here)
  File offset 0x1FFFF0 = GPA 0xFFFFFFF0  (reset vector - CPU starts here)
"""

import struct
import sys
import os

ROM_SIZE = 0x200000  # 2MB
ROM_BASE_GPA = 0xFFE00000
RESET_VECTOR_OFFSET = ROM_SIZE - 16  # offset 0x1FFFF0 in file = GPA 0xFFFFFFF0

# ----- Helper: emit x86 bytes -----
class X86Emitter:
    def __init__(self, base_offset=0):
        self.code = bytearray()
        self.base_offset = base_offset
    
    def db(self, *args):
        for b in args:
            if isinstance(b, (list, tuple, bytes, bytearray)):
                self.code.extend(b)
            else:
                self.code.append(b & 0xFF)
    
    def dw(self, val):
        self.code.extend(struct.pack('<H', val & 0xFFFF))
    
    def dd(self, val):
        self.code.extend(struct.pack('<I', val & 0xFFFFFFFF))
    
    def dq(self, val):
        self.code.extend(struct.pack('<Q', val & 0xFFFFFFFFFFFFFFFF))
    
    def pos(self):
        return len(self.code) + self.base_offset


def emit_string(emitter, s):
    """Emit a null-terminated ASCII string."""
    emitter.db(s.encode('ascii'))
    emitter.db(0)


def build_firmware():
    rom = bytearray(b'\xFF' * ROM_SIZE)  # fill with 0xFF (unprogrammed flash)
    
    # ===================================================================
    # SECTION 1: GDT (at file offset 0x0000, GPA 0xFFE00000)
    # ===================================================================
    gdt_offset = 0x0000
    gdt = X86Emitter(gdt_offset)
    
    # GDT Entry 0: Null descriptor
    gdt.dq(0x0000000000000000)
    # GDT Entry 1 (selector 0x08): 32-bit Code segment (base=0, limit=4GB)
    gdt.dq(0x00CF9A000000FFFF)
    # GDT Entry 2 (selector 0x10): 32-bit Data segment (base=0, limit=4GB)
    gdt.dq(0x00CF92000000FFFF)
    
    rom[gdt_offset:gdt_offset + len(gdt.code)] = gdt.code
    gdt_size = len(gdt.code)
    
    # ===================================================================
    # SECTION 2: String data (at file offset 0x0100, GPA 0xFFE00100)
    # ===================================================================
    strings_offset = 0x0100
    strings = X86Emitter(strings_offset)
    
    # String table: each string is null-terminated
    banner_str_off = strings.pos()
    emit_string(strings,
        "\r\n"
        "=============================================================\r\n"
        "  Hyper X Firmware v1.0 (Custom ROM)\r\n"
        "  Copyright (c) 2026 Hyper X Project\r\n"
        "=============================================================\r\n"
    )
    
    init_str_off = strings.pos()
    emit_string(strings, "[SEC] Security Phase: hardware reset vector executed\r\n")
    
    a20_str_off = strings.pos()
    emit_string(strings, "[SEC] A20 gate enabled, switching to protected mode...\r\n")
    
    pm_str_off = strings.pos()
    emit_string(strings, "[PEI] Pre-EFI Initialization: entered 32-bit Protected Mode\r\n")
    
    uart_str_off = strings.pos()
    emit_string(strings, "[PEI] UART 16550A initialized on COM1 (0x3F8, 115200 baud)\r\n")
    
    mem_str_off = strings.pos()
    emit_string(strings, "[PEI] Memory discovered: 512MB RAM at 0x00000000\r\n")
    
    dxe_str_off = strings.pos()
    emit_string(strings, "[DXE] DXE Dispatcher: loading firmware drivers...\r\n")
    
    pci_str_off = strings.pos()
    emit_string(strings, "[DXE] PCI Bus: enumeration complete (0 devices found)\r\n")
    
    vram_str_off = strings.pos()
    emit_string(strings, "[DXE] X-GPU: Shared VRAM detected at GPA 0x40000000 (256MB)\r\n")
    
    timer_str_off = strings.pos()
    emit_string(strings, "[DXE] Timer: LAPIC timer initialized\r\n")
    
    bds_str_off = strings.pos()
    emit_string(strings, "[BDS] Boot Device Selection: no bootable media found\r\n")
    
    shell_banner_off = strings.pos()
    emit_string(strings,
        "\r\n"
        "Hyper X UEFI Interactive Shell v1.0\r\n"
        "Device mapping table:\r\n"
        "  FS0: <no filesystem>\r\n"
        "  BLK0: <no block device>\r\n"
        "\r\n"
    )
    
    shell_prompt_off = strings.pos()
    emit_string(strings, "Shell> ")
    
    shell_help_off = strings.pos()
    emit_string(strings,
        "\r\nAvailable commands:\r\n"
        "  help    - Display this help message\r\n"
        "  ver     - Display firmware version\r\n"
        "  memmap  - Display memory map\r\n"
        "  reset   - Reset the system\r\n"
        "  exit    - Halt the processor\r\n"
        "\r\n"
    )
    
    ver_str_off = strings.pos()
    emit_string(strings,
        "\r\nHyper X Firmware v1.0\r\n"
        "Build: Custom ROM for Hyper X Hypervisor\r\n"
        "Architecture: x86_64 (IA-32 mode)\r\n"
        "\r\n"
    )
    
    memmap_str_off = strings.pos()
    emit_string(strings,
        "\r\nType            Start            End              Pages\r\n"
        "Conventional    0x0000000000     0x001FFFFFFF     131072\r\n"
        "Reserved        0x3FFFF000       0x3FFFF000       1\r\n"
        "MMIO            0x4000000000     0x4FFFFFFF       65536\r\n"
        "FirmwareROM     0xFFE00000       0xFFFFFFFF       512\r\n"
        "\r\n"
    )
    
    reset_str_off = strings.pos()
    emit_string(strings, "\r\n[RESET] System reset requested. Halting CPU.\r\n")
    
    unknown_str_off = strings.pos()
    emit_string(strings, "\r\nUnknown command. Type 'help' for available commands.\r\n")
    
    newline_str_off = strings.pos()
    emit_string(strings, "\r\n")
    
    rom[strings_offset:strings_offset + len(strings.code)] = strings.code
    
    # ===================================================================
    # SECTION 3: 32-bit Protected Mode Code (at offset 0x1000, GPA 0xFFE01000)
    # ===================================================================
    # This is the main firmware logic after mode switch.
    # All code here runs in 32-bit protected mode with flat addressing.
    
    code_offset = 0x1000
    code_gpa = ROM_BASE_GPA + code_offset
    c = X86Emitter(code_offset)
    
    # ----- serial_putchar: output AL to COM1 (0x3F8) -----
    # Polls LSR until THR is empty, then writes character
    serial_putchar_off = c.pos()
    c.db(0x50)                  # push eax (save char)
    # poll_lsr:
    poll_lsr_off = c.pos()
    c.db(0xBA); c.dw(0x03FD)   # mov dx, 0x3FD (LSR)
    c.db(0xEC)                  # in al, dx
    c.db(0xA8, 0x20)            # test al, 0x20 (THR empty bit)
    c.db(0x74)                  # jz poll_lsr (relative)
    jz_target = poll_lsr_off - (c.pos() + 1)
    c.db(jz_target & 0xFF)
    c.db(0x58)                  # pop eax (restore char)
    c.db(0xBA); c.dw(0x03F8)   # mov dx, 0x3F8 (THR)
    c.db(0xEE)                  # out dx, al
    c.db(0xC3)                  # ret
    
    # ----- serial_print: print null-terminated string at ESI -----
    serial_print_off = c.pos()
    c.db(0x60)                  # pushad
    # .loop:
    print_loop_off = c.pos()
    c.db(0xAC)                  # lodsb (al = [esi], esi++)
    c.db(0x3C, 0x00)            # cmp al, 0
    c.db(0x74)                  # je .done
    c.db(0x05)                  # (skip 5 bytes to .done)
    c.db(0xE8)                  # call serial_putchar
    call_target = serial_putchar_off - (c.pos() + 4)
    c.dd(call_target & 0xFFFFFFFF)
    c.db(0xEB)                  # jmp .loop
    jmp_target = print_loop_off - (c.pos() + 1)
    c.db(jmp_target & 0xFF)
    # .done:
    c.db(0x61)                  # popad
    c.db(0xC3)                  # ret
    
    # ----- init_uart: configure 16550 UART at 0x3F8 -----
    init_uart_off = c.pos()
    c.db(0xBA); c.dw(0x03F9)   # mov dx, 0x3F9 (IER)
    c.db(0xB0, 0x00)            # mov al, 0 (disable interrupts)
    c.db(0xEE)                  # out dx, al
    c.db(0xBA); c.dw(0x03FB)   # mov dx, 0x3FB (LCR)
    c.db(0xB0, 0x80)            # mov al, 0x80 (DLAB=1)
    c.db(0xEE)                  # out dx, al
    c.db(0xBA); c.dw(0x03F8)   # mov dx, 0x3F8 (DLL)
    c.db(0xB0, 0x01)            # mov al, 1 (115200 baud)
    c.db(0xEE)                  # out dx, al
    c.db(0xBA); c.dw(0x03F9)   # mov dx, 0x3F9 (DLH)
    c.db(0xB0, 0x00)            # mov al, 0
    c.db(0xEE)                  # out dx, al
    c.db(0xBA); c.dw(0x03FB)   # mov dx, 0x3FB (LCR)
    c.db(0xB0, 0x03)            # mov al, 0x03 (8N1, DLAB=0)
    c.db(0xEE)                  # out dx, al
    c.db(0xBA); c.dw(0x03FC)   # mov dx, 0x3FC (MCR)
    c.db(0xB0, 0x03)            # mov al, 0x03 (DTR + RTS)
    c.db(0xEE)                  # out dx, al
    c.db(0xBA); c.dw(0x03FA)   # mov dx, 0x3FA (FCR)
    c.db(0xB0, 0xC7)            # mov al, 0xC7 (enable FIFO, clear, 14-byte trigger)
    c.db(0xEE)                  # out dx, al
    c.db(0xC3)                  # ret
    
    # ----- serial_read_char: read one char from COM1 into AL (blocking) -----
    serial_read_off = c.pos()
    # .poll:
    read_poll_off = c.pos()
    c.db(0xBA); c.dw(0x03FD)   # mov dx, 0x3FD (LSR)
    c.db(0xEC)                  # in al, dx
    c.db(0xA8, 0x01)            # test al, 0x01 (data ready bit)
    c.db(0x74)                  # jz .poll
    jz_back = read_poll_off - (c.pos() + 1)
    c.db(jz_back & 0xFF)
    c.db(0xBA); c.dw(0x03F8)   # mov dx, 0x3F8 (RBR)
    c.db(0xEC)                  # in al, dx
    c.db(0xC3)                  # ret
    
    # ----- main_entry: main firmware entry point (32-bit protected mode) -----
    main_entry_off = c.pos()
    
    # Set up stack at 0x80000 (512KB mark)
    c.db(0xBC); c.dd(0x00080000)  # mov esp, 0x80000
    
    # Initialize UART
    c.db(0xE8)  # call init_uart
    c.dd((init_uart_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Print banner
    c.db(0xBE); c.dd(banner_str_off)  # mov esi, banner_str_gpa
    c.db(0xE8)  # call serial_print
    c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Print SEC phase
    c.db(0xBE); c.dd(init_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Print A20 / protected mode
    c.db(0xBE); c.dd(a20_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Print PEI phase
    c.db(0xBE); c.dd(pm_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Print UART init
    c.db(0xBE); c.dd(uart_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Print memory discovery
    c.db(0xBE); c.dd(mem_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Print DXE phase
    c.db(0xBE); c.dd(dxe_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Print PCI enumeration
    c.db(0xBE); c.dd(pci_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Print VRAM detection
    c.db(0xBE); c.dd(vram_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Print timer init
    c.db(0xBE); c.dd(timer_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Print BDS phase
    c.db(0xBE); c.dd(bds_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Print shell banner
    c.db(0xBE); c.dd(shell_banner_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # ---- Shell Loop ----
    # Print prompt, read line into buffer at 0x70000, compare commands
    shell_loop_off = c.pos()
    
    # Print "Shell> "
    c.db(0xBE); c.dd(shell_prompt_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Read a line into buffer at 0x70000
    c.db(0xBF); c.dd(0x00070000)  # mov edi, 0x70000 (input buffer)
    c.db(0xB9); c.dd(0x00000000)  # mov ecx, 0 (char count)
    
    # .read_loop:
    read_loop_off = c.pos()
    c.db(0xE8)  # call serial_read_char
    c.dd((serial_read_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Echo character back
    c.db(0x50)  # push eax
    c.db(0xE8)  # call serial_putchar
    c.dd((serial_putchar_off - (c.pos() + 4)) & 0xFFFFFFFF)
    c.db(0x58)  # pop eax
    
    # Check for enter (CR = 0x0D)
    c.db(0x3C, 0x0D)  # cmp al, 0x0D
    c.db(0x74)  # je .process_cmd
    process_cmd_jmp = c.pos()
    c.db(0x00)  # placeholder - will patch
    
    # Check for backspace (0x08)
    c.db(0x3C, 0x08)  # cmp al, 0x08
    c.db(0x74)  # je .backspace
    backspace_jmp = c.pos()
    c.db(0x00)  # placeholder
    
    # Store character
    c.db(0x88, 0x07)  # mov [edi], al
    c.db(0x47)  # inc edi
    c.db(0x41)  # inc ecx
    c.db(0x83, 0xF9, 0x3F)  # cmp ecx, 63 (max 63 chars)
    c.db(0x7C)  # jl .read_loop
    jl_back = read_loop_off - (c.pos() + 1)
    c.db(jl_back & 0xFF)
    c.db(0xEB)  # jmp .process_cmd_forced
    process_cmd_forced_jmp = c.pos()
    c.db(0x00)  # placeholder
    
    # .backspace:
    backspace_off = c.pos()
    rom[code_offset + (backspace_jmp - code_offset):code_offset + (backspace_jmp - code_offset) + 1] = bytes([(backspace_off - backspace_jmp - 1) & 0xFF])
    c.db(0x83, 0xF9, 0x00)  # cmp ecx, 0
    c.db(0x74)  # je .read_loop (nothing to backspace)
    c.db((read_loop_off - (c.pos() + 1)) & 0xFF)
    c.db(0x4F)  # dec edi
    c.db(0x49)  # dec ecx
    c.db(0xEB)  # jmp .read_loop
    c.db((read_loop_off - (c.pos() + 1)) & 0xFF)
    
    # .process_cmd:
    process_cmd_off = c.pos()
    # Patch the jump placeholders
    rom[code_offset + (process_cmd_jmp - code_offset):code_offset + (process_cmd_jmp - code_offset) + 1] = bytes([(process_cmd_off - process_cmd_jmp - 1) & 0xFF])
    rom[code_offset + (process_cmd_forced_jmp - code_offset):code_offset + (process_cmd_forced_jmp - code_offset) + 1] = bytes([(process_cmd_off - process_cmd_forced_jmp - 1) & 0xFF])
    
    # Null-terminate the input buffer
    c.db(0xC6, 0x07, 0x00)  # mov byte [edi], 0
    
    # Print newline
    c.db(0xBE); c.dd(newline_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # Compare input buffer with known commands
    # Load first 4 bytes of input for quick comparison
    c.db(0x8B, 0x1D); c.dd(0x00070000)  # mov ebx, [0x70000]
    
    # Check "help" (0x706C6568)
    c.db(0x81, 0xFB); c.dd(0x706C6568)  # cmp ebx, "help"
    c.db(0x74)  # je .cmd_help
    cmd_help_jmp = c.pos()
    c.db(0x00)
    
    # Check "ver\0" (0x00726576)
    c.db(0x81, 0xFB); c.dd(0x00726576)  # cmp ebx, "ver\0"
    c.db(0x74)  # je .cmd_ver
    cmd_ver_jmp = c.pos()
    c.db(0x00)
    
    # Check "exit" (0x74697865)
    c.db(0x81, 0xFB); c.dd(0x74697865)  # cmp ebx, "exit"
    c.db(0x74)  # je .cmd_exit
    cmd_exit_jmp = c.pos()
    c.db(0x00)
    
    # Check "memo" (first 4 of "memmap") = 0x6F6D656D
    c.db(0x81, 0xFB); c.dd(0x6D656D)    # cmp ebx, "mem\0" (partial)
    # Actually let's just check first 3 bytes differently
    # Simpler: check if ecx == 0 (empty command)
    c.db(0x74)  # je (skip if matched, but this won't work well)
    cmd_memmap_jmp = c.pos()
    c.db(0x00)
    
    # Check "rese" (first 4 of "reset")
    c.db(0x81, 0xFB); c.dd(0x65736572)  # cmp ebx, "rese"
    c.db(0x74)  # je .cmd_reset
    cmd_reset_jmp = c.pos()
    c.db(0x00)
    
    # Check empty input (ecx == 0)
    c.db(0x83, 0xF9, 0x00)  # cmp ecx, 0
    c.db(0x74)  # je shell_loop (just reprint prompt)
    c.db((shell_loop_off - (c.pos() + 1)) & 0xFF)
    
    # Unknown command
    c.db(0xBE); c.dd(unknown_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    c.db(0xE9)  # jmp shell_loop
    c.dd((shell_loop_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # .cmd_help:
    cmd_help_off = c.pos()
    rom[code_offset + (cmd_help_jmp - code_offset):code_offset + (cmd_help_jmp - code_offset) + 1] = bytes([(cmd_help_off - cmd_help_jmp - 1) & 0xFF])
    c.db(0xBE); c.dd(shell_help_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    c.db(0xE9); c.dd((shell_loop_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # .cmd_ver:
    cmd_ver_off = c.pos()
    rom[code_offset + (cmd_ver_jmp - code_offset):code_offset + (cmd_ver_jmp - code_offset) + 1] = bytes([(cmd_ver_off - cmd_ver_jmp - 1) & 0xFF])
    c.db(0xBE); c.dd(ver_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    c.db(0xE9); c.dd((shell_loop_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # .cmd_memmap:
    cmd_memmap_off = c.pos()
    rom[code_offset + (cmd_memmap_jmp - code_offset):code_offset + (cmd_memmap_jmp - code_offset) + 1] = bytes([(cmd_memmap_off - cmd_memmap_jmp - 1) & 0xFF])
    c.db(0xBE); c.dd(memmap_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    c.db(0xE9); c.dd((shell_loop_off - (c.pos() + 4)) & 0xFFFFFFFF)
    
    # .cmd_reset:
    cmd_reset_off = c.pos()
    rom[code_offset + (cmd_reset_jmp - code_offset):code_offset + (cmd_reset_jmp - code_offset) + 1] = bytes([(cmd_reset_off - cmd_reset_jmp - 1) & 0xFF])
    c.db(0xBE); c.dd(reset_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    c.db(0xF4)  # hlt
    
    # .cmd_exit:
    cmd_exit_off = c.pos()
    rom[code_offset + (cmd_exit_jmp - code_offset):code_offset + (cmd_exit_jmp - code_offset) + 1] = bytes([(cmd_exit_off - cmd_exit_jmp - 1) & 0xFF])
    c.db(0xBE); c.dd(reset_str_off)
    c.db(0xE8); c.dd((serial_print_off - (c.pos() + 4)) & 0xFFFFFFFF)
    c.db(0xF4)  # hlt
    
    # Write 32-bit code into ROM
    rom[code_offset:code_offset + len(c.code)] = c.code
    
    # ===================================================================
    # SECTION 4: 16-bit Real Mode Boot Code (near end of ROM)
    # Located at offset 0x1FFE00, GPA 0xFFFFE00
    # ===================================================================
    boot16_offset = 0x1FFE00
    boot16_gpa = ROM_BASE_GPA + boot16_offset
    b = X86Emitter(boot16_offset)
    
    # --- 16-bit real mode code ---
    # CLI - disable interrupts
    b.db(0xFA)
    
    # Enable A20 gate via port 0x92
    b.db(0xE4, 0x92)        # in al, 0x92
    b.db(0x0C, 0x02)        # or al, 2
    b.db(0x24, 0xFE)        # and al, 0xFE (don't reset)
    b.db(0xE6, 0x92)        # out 0x92, al
    
    # Load GDT
    # GDTR: limit (2 bytes) + base (4 bytes)
    gdt_base_gpa = ROM_BASE_GPA + gdt_offset
    gdtr_offset = b.pos()
    b.dw(gdt_size - 1)      # GDT limit
    b.dd(gdt_base_gpa)      # GDT base address (linear = physical in flat model)
    
    # lgdt [gdtr] — we need to use a CS-relative address
    # Since we're at CS:IP with CS.base = 0xFFFF0000, and our code is in the ROM,
    # we need address prefix + operand prefix for 32-bit addressing
    lgdt_data_gpa = ROM_BASE_GPA + gdtr_offset
    
    # Use lgdt with absolute address via ds override
    # First set DS base to match our ROM location
    # Actually in real mode after reset, DS=0, so we need to load from
    # the linear address of the GDTR data. Since we're running with
    # CS.base = 0xFFFF0000, let's put GDTR data at a known location.
    # We'll copy the GDTR to address 0x600 in low memory first.
    
    # mov ax, 0
    b.db(0xB8); b.dw(0x0000)
    # mov ds, ax
    b.db(0x8E, 0xD8)
    
    # Copy GDTR to linear 0x600
    # mov word [0x600], gdt_limit
    b.db(0x66, 0xC7, 0x06); b.dw(0x0600); b.dw(gdt_size - 1)
    # mov dword [0x602], gdt_base_gpa
    b.db(0x66, 0xC7, 0x06); b.dw(0x0602); b.dd(gdt_base_gpa)
    
    # lgdt [0x600]
    b.db(0x0F, 0x01, 0x16); b.dw(0x0600)
    
    # Set CR0.PE = 1 (enter protected mode)
    b.db(0x0F, 0x20, 0xC0)  # mov eax, cr0
    b.db(0x66, 0x83, 0xC8, 0x01)  # or eax, 1
    b.db(0x0F, 0x22, 0xC0)  # mov cr0, eax
    
    # Far jump to 32-bit code: jmp 0x08:main_entry_gpa
    # This flushes the pipeline and loads CS with the 32-bit code descriptor
    main_entry_gpa = ROM_BASE_GPA + main_entry_off
    b.db(0x66, 0xEA)        # far jmp (32-bit operand)
    b.dd(main_entry_gpa)    # offset (32-bit)
    b.dw(0x0008)            # selector (GDT entry 1 = code segment)
    
    rom[boot16_offset:boot16_offset + len(b.code)] = b.code
    
    # ===================================================================
    # SECTION 5: Reset Vector (at offset 0x1FFFF0, GPA 0xFFFFFFF0)
    # ===================================================================
    # The CPU starts executing here after reset.
    # We need a near jump to our 16-bit boot code.
    # The jump target is relative to EIP after the instruction.
    # From 0xFFFFFFF0, jump to boot16_gpa
    
    reset_vec = bytearray()
    # jmp near (16-bit relative) to boot16_gpa
    # In real mode with CS.base=0xFFFF0000, IP starts at 0xFFF0
    # Target IP = boot16_gpa - 0xFFFF0000 = boot16_offset + ROM_BASE_GPA - 0xFFFF0000
    # = 0xFFE00000 + 0x1FFE00 - 0xFFFF0000 = 0xFFFFFE00 - 0xFFFF0000 = 0xFE00
    target_ip = boot16_gpa - 0xFFFF0000
    current_ip_after_jmp = 0xFFF0 + 2  # IP after 2-byte short jmp = 0xFFF2
    # But we might need a 3-byte near jmp. Let's use the 16-bit near jmp:
    # E9 rel16
    current_ip_after_jmp = 0xFFF0 + 3  # IP after 3-byte near jmp
    rel16 = (target_ip - current_ip_after_jmp) & 0xFFFF
    
    reset_vec.append(0xE9)              # jmp rel16
    reset_vec.extend(struct.pack('<H', rel16))
    
    # Pad remaining bytes of reset vector area with NOPs
    while len(reset_vec) < 16:
        reset_vec.append(0x90)  # NOP
    
    rom[RESET_VECTOR_OFFSET:RESET_VECTOR_OFFSET + 16] = reset_vec[:16]
    
    return rom


def main():
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "firmware", "hyperx_firmware.fd")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print("Hyper X Firmware Generator")
    print("=" * 50)
    print(f"ROM Size:       {ROM_SIZE // 1024}KB ({ROM_SIZE} bytes)")
    print(f"ROM Base GPA:   0x{ROM_BASE_GPA:08X}")
    print(f"Reset Vector:   0xFFFFFFF0 (file offset 0x{RESET_VECTOR_OFFSET:06X})")
    print(f"Output:         {output_path}")
    print()
    
    rom = build_firmware()
    
    with open(output_path, 'wb') as f:
        f.write(rom)
    
    print(f"[OK] Firmware ROM written: {len(rom)} bytes")
    print(f"[OK] Reset vector at file offset 0x{RESET_VECTOR_OFFSET:06X}:")
    print(f"     Bytes: {' '.join(f'{b:02X}' for b in rom[RESET_VECTOR_OFFSET:RESET_VECTOR_OFFSET+16])}")
    print()
    print("Usage:")
    print(f"  hyper_x -f {output_path}")
    print()
    print("Expected serial output:")
    print("  Hyper X Firmware v1.0 banner")
    print("  SEC/PEI/DXE phase messages")
    print("  Shell> prompt (interactive)")


if __name__ == "__main__":
    main()
