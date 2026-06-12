import re
import sys

hue, text, bg, on = sys.argv[1:5]
p = r"F:\Surprise App\ui\css\app.css"
s = open(p, encoding="utf-8").read()
s = re.sub(r"--accent: #[0-9a-fA-F]+;", f"--accent: {hue};", s, count=1)
s = re.sub(r"--accent-text: #[0-9a-fA-F]+;", f"--accent-text: {text};", s, count=1)
s = re.sub(r"--accent-bg: rgba\([^)]*\);", f"--accent-bg: {bg};", s, count=1)
s = re.sub(r"--on-accent: #[0-9a-fA-F]+;", f"--on-accent: {on};", s, count=1)
open(p, "w", encoding="utf-8", newline="").write(s)
print("set", hue)
