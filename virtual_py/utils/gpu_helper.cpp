#include <iostream>
#include <vector>
#include <string>

#ifdef _WIN32
#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "d3d11.lib")
#else
#include <filesystem>
#include <fstream>
#include <sstream>
namespace fs = std::filesystem;
#endif

int main() {
#ifdef _WIN32
    CoInitialize(nullptr);
    IDXGIFactory* pFactory = nullptr;
    if (FAILED(CreateDXGIFactory(__uuidof(IDXGIFactory), (void**)&pFactory))) {
        std::cerr << "failed to create dxgi factory" << std::endl;
        return 1;
    }

    IDXGIAdapter* pAdapter = nullptr;
    bool found = false;
    for (UINT i = 0; pFactory->EnumAdapters(i, &pAdapter) != DXGI_ERROR_NOT_FOUND; ++i) {
        DXGI_ADAPTER_DESC desc;
        pAdapter->GetDesc(&desc);
        
        char description[128];
        WideCharToMultiByte(CP_UTF8, 0, desc.Description, -1, description, sizeof(description), nullptr, nullptr);
        
        std::cout << "gpu:" << description << "|"
                  << "vendor_id:0x" << std::hex << desc.VendorId << "|"
                  << "device_id:0x" << desc.DeviceId << "|"
                  << "vram_mb:" << std::dec << (desc.DedicatedVideoMemory / (1024 * 1024)) << "|"
                  << "pci_address:0000:00:00.0" << std::endl;
        pAdapter->Release();
        found = true;
    }
    pFactory->Release();
    CoUninitialize();
    if (!found) {
        std::cout << "no gpus found" << std::endl;
    }
#else
    bool found = false;
    std::string pci_path = "/sys/bus/pci/devices";
    if (fs::exists(pci_path)) {
        for (const auto& entry : fs::directory_iterator(pci_path)) {
            std::string class_file = entry.path().string() + "/class";
            std::string class_val;
            std::ifstream infile(class_file);
            if (infile >> class_val) {
                if (class_val.rfind("0x03", 0) == 0) {
                    std::string pci_addr = entry.path().filename().string();
                    std::cout << "gpu:Linux PCI Graphics Adapter|"
                              << "vendor_id:0x0000|"
                              << "device_id:0x0000|"
                              << "vram_mb:0|"
                              << "pci_address:" << pci_addr << std::endl;
                    found = true;
                }
            }
        }
    }
    if (!found) {
        std::cout << "no gpus found" << std::endl;
    }
#endif
    return 0;
}
