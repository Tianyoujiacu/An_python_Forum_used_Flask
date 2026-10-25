"""生成闸门口令哈希：python3 gate_password.py '你的口令'

把输出填进 PA 的环境变量 GATE_PASSWORD_HASH 即可（每次运行结果都不同，都有效）。
"""
import sys
from werkzeug.security import generate_password_hash

if len(sys.argv) != 2 or not sys.argv[1].strip():
    print("用法：python3 gate_password.py '口令'   （口令至少 10 位更稳妥）")
    raise SystemExit(1)
pw = sys.argv[1]
if len(pw) < 8:
    print("提示：短于 8 位，闸门等于没关。")
print("GATE_PASSWORD_HASH=" + generate_password_hash(pw))