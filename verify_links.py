import urllib.request
import urllib.error
import os
import concurrent.futures
import sys

# Append current dir to sys.path so we can import virtual_py
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from virtual_py.catalog import default_registry

def check_link(template):
    url = template.url
    try:
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status in (200, 302, 301):
                return (template.id, url, "OK", True)
    except urllib.error.HTTPError as e:
        return (template.id, url, f"ERROR: {e.code}", False)
    except Exception as e:
        return (template.id, url, f"ERROR: {e}", False)
    return (template.id, url, "UNKNOWN", False)

def main():
    templates = default_registry.list_all()
    print(f"Checking {len(templates)} templates...")
    
    unavailable_templates = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_tpl = {executor.submit(check_link, t): t for t in templates}
        for future in concurrent.futures.as_completed(future_to_tpl):
            tid, url, status, is_available = future.result()
            if is_available:
                print(f"[OK] {tid}")
            else:
                print(f"[UNAVAILABLE] {tid} ({status}): {url}")
                unavailable_templates.append(tid)
                
    if unavailable_templates:
        print(f"\nMarking {len(unavailable_templates)} templates as unavailable in Python files...")
        dirs_to_check = ["virtual_py/catalog/linux", "virtual_py/catalog/windows"]
        for d in dirs_to_check:
            for fname in os.listdir(d):
                if fname.endswith(".py") and fname != "__init__.py":
                    fpath = os.path.join(d, fname)
                    with open(fpath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    changed = False
                    for tid in unavailable_templates:
                        # Extract the exact ID being checked
                        # we need to safely find where this ID is used.
                        # Since template filenames usually match tid (e.g. centos_9_stream.py for centos-9-stream)
                        # We can just look for id="<tid>"
                        id_str = f'id="{tid}"'
                        if id_str in content and "available=False" not in content:
                            # Replace closing parenthesis of OSTemplate instantiation with available=False)
                            # This is a basic string replacement that handles the auto-generated templates.
                            # Usually ends with: default_username="xxx"\n)
                            # We can inject available=False before the closing paren.
                            content = content.replace(')\n', ',\n    available=False\n)\n', 1)
                            
                            # If it didn't match the standard `)\n`, fallback to regex
                            if ',\n    available=False\n)\n' not in content:
                                import re
                                content = re.sub(r'(\s*)\)$', r',\n    available=False\1)', content, flags=re.MULTILINE)
                            
                            changed = True
                            
                    if changed:
                        with open(fpath, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"Updated {fpath}")
        print("Done.")
    else:
        print("\nAll links are available.")

if __name__ == "__main__":
    main()
