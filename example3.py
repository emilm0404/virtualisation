import subprocess
import sys
import os
import shutil

def build_and_run():
    print("[python VMM] configuring hyper-x project via cmake...")
    build_dir = os.path.join("hyper_x", "build")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir, exist_ok=True)

    # configure cmake
    try:
        subprocess.run(["cmake", ".."], cwd=build_dir, check=True)
    except Exception as e:
        print(f"[python VMM] error: cmake configuration failed: {e}")
        return

    print("[python VMM] compiling hyper-x executable...")
    try:
        subprocess.run(["cmake", "--build", "."], cwd=build_dir, check=True)
    except Exception as e:
        print(f"[python VMM] error: compilation failed: {e}")
        return

    # locate built executable
    exe_name = "hyper_x"
    if sys.platform == "win32":
        exe_name += ".exe"
    
    # search standard build output paths
    exe_paths = [
        os.path.join(build_dir, exe_name),
        os.path.join(build_dir, "Debug", exe_name),
        os.path.join(build_dir, "Release", exe_name)
    ]
    
    exe_path = None
    for p in exe_paths:
        if os.path.exists(p):
            exe_path = p
            break
            
    if not exe_path:
        print("[python VMM] error: could not locate built hyper-x executable.")
        return

    print(f"[python VMM] starting VM execution via {exe_path}...")
    try:
        proc = subprocess.Popen([exe_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        # stream logs in real-time to stdout
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
        proc.wait()
        print(f"[python VMM] VM execution terminated with code {proc.returncode}")
    except Exception as e:
        print(f"[python VMM] error during execution: {e}")

if __name__ == "__main__":
    build_and_run()
