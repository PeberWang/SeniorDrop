"""Convert setup.bat / start.bat to GBK so Windows cmd parses them correctly.

背景：Windows cmd 按系统代码页（中国版 = GBK/936）解析 .bat 文件字节，
chcp 65001 只改控制台输出编码，不改文件读取编码。
UTF-8 编码的 .bat 在 cmd 里会出现中文行被切碎、报 'XXX' is not recognized 的假错误。
本脚本把含中文的 .bat 转为 GBK 并删除多余的 chcp 65001 行。
"""
import sys
from pathlib import Path

TARGETS = ["setup.bat", "start.bat"]


def convert(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    lines = [
        line
        for line in text.splitlines(keepends=True)
        if not line.strip().lower().startswith("chcp 65001")
    ]
    new_content = "".join(lines).replace("\r\n", "\n").replace("\n", "\r\n")
    path.write_text(new_content, encoding="gbk", newline="")
    print(f"converted {path.name} to GBK, removed chcp 65001")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    rc = 0
    for name in TARGETS:
        p = root / name
        if not p.exists():
            print(f"skip (missing): {name}", file=sys.stderr)
            rc = 1
            continue
        convert(p)
    return rc


if __name__ == "__main__":
    sys.exit(main())
