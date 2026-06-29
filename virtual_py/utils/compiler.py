import subprocess
import shutil
import sys
import os

def get_gpu_helper_binary_path() -> str:
    dir_path = os.path.dirname(__file__)
    binary_name = "gpu_helper.exe" if sys.platform == "win32" else "gpu_helper"
    return os.path.join(dir_path, binary_name)

def compile_gpu_helper():
    binary_path = get_gpu_helper_binary_path()
    if os.path.exists(binary_path):
        return binary_path
    
    dir_path = os.path.dirname(__file__)
    src_path = os.path.join(dir_path, "gpu_helper.cpp")
    
    if sys.platform == "win32":
        cl_path = shutil.which("cl")
        gxx_path = shutil.which("g++")
        if cl_path:
            subprocess.run(["cl", "/EHsc", "/O2", "/Fe:" + binary_path, src_path], cwd=dir_path, capture_output=True)
            obj_path = binary_path.replace(".exe", ".obj")
            if os.path.exists(obj_path):
                os.remove(obj_path)
        elif gxx_path:
            subprocess.run(["g++", "-O2", "-o", binary_path, src_path, "-ldxgi", "-ld3d11"], capture_output=True)
        else:
            # return fallback path. compilation will fail on execution.
            pass
    else:
        gxx_path = shutil.which("g++")
        if gxx_path:
            subprocess.run(["g++", "-O2", "-std=c++17", "-o", binary_path, src_path], capture_output=True)
            
    return binary_path
