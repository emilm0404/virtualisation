#include "../include/xgpu_protocol.h"
#include <fcntl.h>
#if defined(_WIN32) || defined(_WIN64)
#include <io.h>
#else
#include <unistd.h>
#endif

typedef void* VkInstance;
typedef void* VkDevice;
typedef void* VkQueue;
typedef uint32_t VkResult;

#if !defined(_WIN32) && !defined(_WIN64)
#define EXPORT
#else
#define EXPORT __declspec(dllexport)
#endif

extern "C" {

EXPORT VkResult vkCreateInstance(const void* pCreateInfo, const void* pAllocator, VkInstance* pInstance) {
#if !defined(_WIN32) && !defined(_WIN64)
    int fd = open("/dev/hyperx_drm", O_WRONLY);
    if (fd >= 0) {
        XGpuCommand cmd;
        cmd.command_id = XGPU_CMD_INIT;
        cmd.payload_size = 0;
        cmd.vram_offset = 0;
        write(fd, &cmd, sizeof(cmd));
        close(fd);
    }
#endif
    *pInstance = (VkInstance)0xDEADBEEF;
    return 0;
}

EXPORT VkResult vkAllocateMemory(VkDevice device, const void* pAllocateInfo, const void* pAllocator, void** pMemory) {
#if !defined(_WIN32) && !defined(_WIN64)
    int fd = open("/dev/hyperx_drm", O_WRONLY);
    if (fd >= 0) {
        XGpuCommand cmd;
        cmd.command_id = XGPU_CMD_ALLOC_MEM;
        cmd.payload_size = 1024;
        cmd.vram_offset = 0x1000;
        write(fd, &cmd, sizeof(cmd));
        close(fd);
    }
#endif
    *pMemory = (void*)0x40001000;
    return 0;
}

EXPORT VkResult vkQueueSubmit(VkQueue queue, uint32_t submitCount, const void* pSubmits, void* fence) {
#if !defined(_WIN32) && !defined(_WIN64)
    int fd = open("/dev/hyperx_drm", O_WRONLY);
    if (fd >= 0) {
        XGpuCommand cmd;
        cmd.command_id = XGPU_CMD_VK_SUBMIT;
        cmd.payload_size = 256;
        cmd.vram_offset = 0x2000;
        write(fd, &cmd, sizeof(cmd));
        close(fd);
    }
#endif
    return 0;
}

}
