import subprocess
import sys
from pathlib import Path

result = subprocess.check_output(
    [sys.executable, "-m", "pip", "freeze"],
    text=True,
)

lines = []
for line in result.splitlines():
    if line.lower().startswith("pywinpty=="):
        line += '; sys_platform == "win32"'
    lines.append(line)

if not any(line.lower().startswith("gunicorn==") for line in lines):
    lines.append("gunicorn")

Path("requirements.txt").write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8",
)