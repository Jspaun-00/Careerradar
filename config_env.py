import os
from pathlib import Path

def load_env_file(env_path: str = ".env"):
    """
    Lightweight zero-dependency .env loader.
    Reads key=value pairs into os.environ if not already set.
    """
    p = Path(env_path)
    if not p.is_file():
        return
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                # Strip wrapping single/double quotes if present
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        print(f"[Warning] Failed reading {env_path}: {e}")

# Automatically load on import
load_env_file()
