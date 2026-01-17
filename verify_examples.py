import subprocess
import sys
import os

CHECKS = [
    {
        "file": "examples/hello_world.ckr",
        "expected_snippet": "Hello World",
        "description": "Basic Hello World"
    },
    {
        "file": "examples/hello_fun_world.ckr",
        "expected_snippet": "Hello World",
        "description": "Rectangular Hello World"
    },
    {
        "file": "examples/gugu_dan.ckr",
        "expected_snippet": "2 x 1 = 2",
        "description": "Gugu-Dan Multiplication Table"
    }
]

def verify():
    print("=== CKR-Lang Example Verification ===\n")
    failed = False
    
    for check in CHECKS:
        filename = check["file"]
        desc = check["description"]
        expected = check["expected_snippet"]
        
        print(f"Running {desc} ({filename})...")
        
        if not os.path.exists(filename):
            print(f"  [MISSING] File not found: {filename}")
            failed = True
            continue
            
        try:
            # Execute CKR script using the module
            result = subprocess.run(
                [sys.executable, "-m", "ckr_lang", filename],
                capture_output=True,
                text=True,
                encoding='utf-8',
                check=True
            )
            
            output = result.stdout.strip()
            
            # Simple containment check
            if expected in output:
                print(f"  [PASS] Output contains '{expected}'")
                # For Gugu-dan, check end too
                if filename == "examples/gugu_dan.ckr":
                    if "9 x 9 = 81" in output:
                         print(f"  [PASS] Output contains '9 x 9 = 81'")
                    else:
                         print(f"  [FAIL] Missing end of table '9 x 9 = 81'")
                         failed = True
            else:
                print(f"  [FAIL] Expected '{expected}' not found.")
                print("  --- captured output ---")
                print(output)
                print("  -----------------------")
                failed = True
                
        except subprocess.CalledProcessError as e:
            print(f"  [ERROR] Execution failed with code {e.returncode}")
            print(e.stderr)
            failed = True
        except Exception as e:
            print(f"  [ERROR] Unexpected error: {e}")
            failed = True
            
        print("-" * 40)

    if failed:
        print("\n❌ Verification Failed!")
        sys.exit(1)
    else:
        print("\n✅ All Examples Verified Successfully!")
        sys.exit(0)

if __name__ == "__main__":
    verify()
