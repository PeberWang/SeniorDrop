# PPE云端智能大礼包 - Issue日志

## 记录原则
- **Issue = 执行时出现的报错**，不是待决策事项
- 遇到报错先记录，自主探索解决方案
- 解决后记录原因和方法
- **目的**：提升自我纠错能力，减轻用户技术负担

---

## Issue #1: UnicodeEncodeError - GBK 编码无法输出 Emoji

### 错误信息
```
UnicodeEncodeError: 'gbk' codec can't encode character '\u2705' in position 0: illegal multibyte sequence
```

### 出现位置
- `daily_task.py` - 2026-02-19 20:42
- `analyze_policies.py` - 2026-02-19 21:14
- `gen_html.py` - 2026-02-19 21:46

### 原因分析
Windows PowerShell 默认使用 **GBK 编码**（Code Page 936），无法输出 Unicode Emoji 字符。当 Python 脚本尝试 `print()` 包含 emoji 的字符串时，会触发此错误。

### 解决方案
在脚本开头添加以下代码，强制使用 UTF-8 编码：

```python
import sys
import io

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
```

### 状态
- ✅ `daily_task.py` - 已修复 (2026-02-19)
- ✅ `analyze_policies.py` - 已修复 (2026-02-19)
- 🔄 `gen_html.py` - 待修复

---

## Issue #2: ModuleNotFoundError - tabulate 模块缺失

### 错误信息
```
ImportError: `Import tabulate` failed. Use pip or conda to install the tabulate package.
```

### 出现位置
- `analyze_policies.py` 第169行 - 调用 `df.to_markdown()`

### 原因分析
pandas 的 `to_markdown()` 方法依赖 `tabulate` 库，但该库未安装。

### 解决方案
```bash
pip install tabulate
```

或在代码中避免使用 `to_markdown()`，改用其他输出方式。

### 状态
- ⏳ 待安装 tabulate 或修改代码

---

## 记录

### 2026-02-18 21:35
- 澄清Issue定义：执行报错，非决策点
- 移除"待确认事项"（应属于需求确认，不是Issue）
