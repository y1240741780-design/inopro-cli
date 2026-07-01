# InoProShop CLI

> 便携式 InoProShop PLC 操控工具 — 一个 Python 文件，让 AI（Trae/Claude/Cursor）直接操控汇川 PLC 编程软件

[![Python](https://img.shields.io/badge/Python-3.7+-blue)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()

---

## 这是什么

从 [InoProShop LIMIT MCP](https://github.com/LIMIT-LMT/InoProShop_LIMIT_MCP) 提取核心 IronPython 引擎重构的 CLI 工具。

**不需要** MCP 协议、**不需要** Node.js、**不需要** Claude Desktop。纯 Python，一个文件，任何能跑终端命令的 AI 工具都能用它操控 InoProShop。

## 跨电脑即插即用

```
1. 复制 inopro.py 到目标电脑
2. 确保 Python 3.7+ 已安装（Windows 自带或装一个）
3. 直接运行 → 首次自动检测 InoProShop 安装路径
4. 完事。
```

## 快速开始

```bash
# 查看帮助
python inopro.py

# 检查 InoProShop 状态
python inopro.py status

# 打开工程
python inopro.py open "D:\Projects\MyPLC.project"

# 创建 POU
python inopro.py create-pou MotorCtrl FunctionBlock st

# 写入代码
python inopro.py set-code MotorCtrl "VAR x:INT; END_VAR" "x := x + 1;"

# 编译
python inopro.py compile

# 查看结构
python inopro.py structure
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `open <路径>` | 打开 .project 工程文件 |
| `compile` | 编译工程，返回真实错误及行号 |
| `structure` | 查看工程完整对象树 |
| `create-pou <名> <类型> [语言]` | 创建 Program / FunctionBlock / Function |
| `set-code <路径> <声明> <实现>` | 写入 VAR 声明 + ST 实现代码 |
| `get-code <路径>` | 读取 POU 声明和实现 |
| `create-task <名> [周期us] [优先级]` | 创建任务 |
| `raw <代码>` | 直接执行 IronPython 脚本 |
| `config` | 显示当前配置 |
| `status` | 检查 InoProShop 连接状态 |

## 在 Trae 中使用

Trae 不支持 MCP，但支持终端命令。把这个文件放到电脑上，然后在 Trae 里这样用：

```
"帮我用 inopro.py 打开 D:\Projects\Test.project，创建一个 Motor 的 FB"
```

Trae 会依次执行：
```bash
python inopro.py open "D:\Projects\Test.project"
python inopro.py create-pou Motor FunctionBlock st
```

## 手动配置

如果自动检测失败，两种方式手动指定路径：

**方式一：环境变量**
```powershell
set INOPRO_PATH=D:\Inovance Control\InoProShop\CODESYS\Common\InoProShop.exe
```

**方式二：配置文件**
在 inopro.py 同目录创建 `inopro_config.json`：
```json
{
  "exe": "D:\\Inovance Control\\InoProShop\\CODESYS\\Common\\InoProShop.exe",
  "profile": "InoProShop(V1.9.1.6)"
}
```

## 适配设备

汇川中型 PLC: AM400 / AM500 / AM600 系列  
InoProShop V1.9.1.6 (SP11 内核)

## 致谢

基于 [LIMIT-LMT/InoProShop_LIMIT_MCP](https://github.com/LIMIT-LMT/InoProShop_LIMIT_MCP) 重构，感谢原作者。
