#pragma once
#include <cstdint>

#define XGPU_CMD_INIT      0x01
#define XGPU_CMD_ALLOC_MEM 0x02
#define XGPU_CMD_VK_SUBMIT 0x03

#pragma pack(push, 1)
struct XGpuCommand {
    uint32_t command_id;
    uint32_t payload_size;
    uint32_t vram_offset;
};
#pragma pack(pop)
