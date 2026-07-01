"""
InoProShop CLI — 便携式 InoProShop 操控工具
============================================
用于 Trae / Claude Code / Cursor / 终端 直接操控汇川 InoProShop PLC 编程软件。

无需 MCP 协议，无需 Node.js，纯 Python，零依赖，一个文件走天下。

用法:
  python inopro.py open <工程路径>              打开工程
  python inopro.py compile                       编译工程
  python inopro.py create-pou <名> <类型> [语言] [父路径]  创建POU
  python inopro.py set-code <路径> <声明> <实现>          写入代码
  python inopro.py get-code <路径>                        读取代码
  python inopro.py create-task <名> [周期us] [优先级]      创建任务
  python inopro.py raw <IronPython代码>                   直接执行

跨电脑使用:
  1. 复制 inopro.py 到目标电脑
  2. 确保 Python 3.7+ 已安装
  3. 直接运行 — 首次运行自动检测 InoProShop 路径
  4. 也可手动设置环境变量 INOPRO_PATH 覆盖自动检测

作者: 基于 LIMIT-LMT/InoProShop_LIMIT_MCP 重构
"""
import sys
import os
import subprocess
import time
import tempfile
import json

VERSION = "1.0.0"

# ========== 自动检测 InoProShop ==========


def find_inopro():
    """自动查找 InoProShop.exe 安装位置"""
    # 1. 环境变量优先
    env_path = os.environ.get("INOPRO_PATH", "")
    if env_path and os.path.exists(env_path):
        return env_path, _detect_profile(env_path)

    # 2. 常见安装路径
    candidates = [
        r"D:\Inovance Control\InoProShop\CODESYS\Common\InoProShop.exe",
        r"C:\Inovance Control\InoProShop\CODESYS\Common\InoProShop.exe",
        r"E:\Inovance Control\InoProShop\CODESYS\Common\InoProShop.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p, _detect_profile(p)

    # 3. 搜索 Program Files (限定深度避免太慢)
    search_roots = ["C:/Program Files", "C:/Program Files (x86)", "D:/", "E:/"]
    for root in search_roots:
        if not os.path.exists(root):
            continue
        try:
            for dirpath, dirs, files in os.walk(root):
                if "InoProShop.exe" in files:
                    path = os.path.join(dirpath, "InoProShop.exe")
                    return path, _detect_profile(path)
                # 限制深度
                depth = dirpath.replace(root, "").count(os.sep)
                if depth > 4:
                    dirs.clear()
        except PermissionError:
            continue

    return None, None


def _detect_profile(exe_path):
    """检测 InoProShop 版本/profile"""
    base = os.path.dirname(os.path.dirname(exe_path))
    version_files = [
        os.path.join(base, "version.txt"),
        os.path.join(base, "..", "version.txt"),
    ]
    for vf in version_files:
        try:
            with open(vf) as f:
                content = f.read()
                if "1.9" in content:
                    return "InoProShop(V1.9.1.6)"
                if "1.8" in content or "1.7" in content:
                    return "InoProShop(V1.8.1.3)"
        except Exception:
            pass
    return "InoProShop(V1.8.1.3)"


def get_config():
    """获取配置，优先使用配置文件，其次自动检测"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, "inopro_config.json")
    config = {"exe": None, "profile": "InoProShop(V1.8.1.3)"}

    if os.path.exists(config_file):
        try:
            with open(config_file) as f:
                config.update(json.load(f))
        except Exception:
            pass

    # 如果配置无效，自动检测
    if not config["exe"] or not os.path.exists(config["exe"]):
        exe, profile = find_inopro()
        if exe:
            config["exe"] = exe
            if profile:
                config["profile"] = profile
            # 保存配置
            try:
                with open(config_file, "w") as f:
                    json.dump(config, f, indent=2)
            except Exception:
                pass

    return config


# ========== IronPython 脚本头部 ==========

SCRIPT_HEADER = r"""# -*- coding: utf-8 -*-
import sys as _sys, os as _os, traceback as _tb
import scriptengine as _se_hdr
try: _se_hdr.system.prompt_handling = _se_hdr.PromptHandling.ProcessScriptPrompts
except Exception: pass
_RESULT_FILE = r'{}'
def rlog(s):
    try:
        with open(_RESULT_FILE, 'ab') as _f:
            _f.write((str(s)+'\n').encode('utf-8'))
    except Exception: pass

"""


# ========== IronPython 脚本模板 ==========


def script_open_project(project_path):
    return """
PROJECT_FILE_PATH = r'{}'
try:
    proj = script_engine.projects.open(PROJECT_FILE_PATH)
    if proj:
        rlog("Project Opened: " + str(proj.get_name()))
        rlog("SCRIPT_SUCCESS: Project opened successfully.")
    else:
        rlog("SCRIPT_ERROR: open() returned None")
    _sys.exit(0)
except Exception as e:
    rlog("SCRIPT_ERROR: " + str(e))
    _sys.exit(1)
""".format(project_path)


def script_compile():
    return """
try:
    primary = script_engine.projects.primary
    app = primary.active_application
    result = app.compile()
    if hasattr(result, 'error_count') and result.error_count > 0:
        for err in result.errors:
            rlog("ERROR: %s line %s: %s" % (err.object_name, err.line, err.message))
        rlog("SCRIPT_ERROR: Compile failed with %s errors" % result.error_count)
    else:
        rlog("SCRIPT_SUCCESS: Compile succeeded, 0 errors.")
    _sys.exit(0)
except Exception as e:
    rlog("SCRIPT_ERROR: " + str(e))
    _sys.exit(1)
"""


def script_create_pou(name, pou_type, language="st", parent=""):
    return """
POU_NAME = '{}'
POU_TYPE = '{}'
POU_LANG = '{}'
PARENT = '{}' if '{}' else ''

try:
    primary = script_engine.projects.primary
    app = primary.active_application
    if PARENT:
        from scriptengine.projects import get_object_by_path
        parent_obj = get_object_by_path(primary, PARENT)
        if parent_obj is None:
            rlog("SCRIPT_ERROR: Parent not found: " + PARENT)
            _sys.exit(1)
    else:
        parent_obj = app

    new_pou = parent_obj.create_pou(POU_NAME, POU_TYPE, POU_LANG)
    if new_pou:
        primary.save()
        rlog("POU Created: " + POU_NAME)
        rlog("SCRIPT_SUCCESS: POU created successfully.")
    else:
        rlog("SCRIPT_ERROR: create_pou returned None")
    _sys.exit(0)
except Exception as e:
    rlog("SCRIPT_ERROR: " + str(e))
    _sys.exit(1)
""".format(name, pou_type, language, parent, parent)


def script_set_pou_code(pou_path, declarations, implementation):
    # 转义单引号和反斜杠
    decl = declarations.replace("\\", "\\\\").replace("'", "\\'")
    impl = implementation.replace("\\", "\\\\").replace("'", "\\'")
    return """
POU_PATH = '{}'

try:
    primary = script_engine.projects.primary
    from scriptengine.projects import get_object_by_path
    obj = get_object_by_path(primary, POU_PATH)
    if obj is None:
        rlog("SCRIPT_ERROR: Object not found: " + POU_PATH)
        _sys.exit(1)

    decl_str = '{}'
    impl_str = '{}'

    if decl_str and decl_str != 'None':
        obj.declarations = decl_str
    if impl_str and impl_str != 'None':
        obj.implementation = impl_str

    primary.save()
    rlog("Code Set For: " + POU_PATH)
    rlog("SCRIPT_SUCCESS: Code set successfully.")
    _sys.exit(0)
except Exception as e:
    import traceback
    rlog("SCRIPT_ERROR: " + str(e))
    rlog(traceback.format_exc())
    _sys.exit(1)
""".format(pou_path, decl, impl)


def script_get_pou_code(pou_path):
    return """
POU_PATH = '{}'
try:
    primary = script_engine.projects.primary
    from scriptengine.projects import get_object_by_path
    obj = get_object_by_path(primary, POU_PATH)
    if obj is None:
        rlog("SCRIPT_ERROR: Object not found: " + POU_PATH)
        _sys.exit(1)

    decl = obj.declarations if hasattr(obj, 'declarations') else ''
    impl = obj.implementation if hasattr(obj, 'implementation') else ''
    rlog("=== DECLARATIONS ===")
    rlog(str(decl))
    rlog("=== IMPLEMENTATION ===")
    rlog(str(impl))
    rlog("SCRIPT_SUCCESS")
    _sys.exit(0)
except Exception as e:
    rlog("SCRIPT_ERROR: " + str(e))
    _sys.exit(1)
""".format(pou_path)


def script_get_structure():
    return """
try:
    primary = script_engine.projects.primary

    def walk(obj, depth=0):
        prefix = "  " * depth
        name = obj.get_name() if hasattr(obj, 'get_name') else str(obj)
        obj_type = type(obj).__name__
        rlog(prefix + "|- " + name + " [" + obj_type + "]")
        if hasattr(obj, 'get_children'):
            for child in obj.get_children():
                walk(child, depth + 1)

    rlog("=== PROJECT STRUCTURE ===")
    walk(primary)
    rlog("SCRIPT_SUCCESS")
    _sys.exit(0)
except Exception as e:
    rlog("SCRIPT_ERROR: " + str(e))
    _sys.exit(1)
"""


def script_create_task(name, interval_us=4000, priority=1):
    return """
TASK_NAME = '{}'
INTERVAL_US = {}
PRIORITY = {}
try:
    primary = script_engine.projects.primary
    app = primary.active_application
    task_config = None
    for child in app.get_children():
        if 'task' in type(child).__name__.lower():
            task_config = child
            break
    if task_config is None:
        rlog("SCRIPT_ERROR: TaskConfiguration not found")
        _sys.exit(1)

    new_task = task_config.create_task(TASK_NAME, INTERVAL_US, PRIORITY)
    if new_task:
        primary.save()
        rlog("Task Created: " + TASK_NAME)
        rlog("SCRIPT_SUCCESS: Task created successfully.")
    else:
        rlog("SCRIPT_ERROR: create_task returned None")
    _sys.exit(0)
except Exception as e:
    rlog("SCRIPT_ERROR: " + str(e))
    _sys.exit(1)
""".format(name, interval_us, priority)


# ========== 执行引擎 ==========


def run_ironpython(script_body, live=False):
    """执行 IronPython 脚本，返回 (success, output)

    live=True: 执行后保持 InoProShop 打开，可实时查看结果
    """
    config = get_config()
    exe = config["exe"]
    prof = config["profile"]

    if not exe or not os.path.exists(exe):
        return False, (
            "ERROR: InoProShop.exe not found!\n"
            "请设置环境变量 INOPRO_PATH 或创建 inopro_config.json:\n"
            '{\n  "exe": "D:\\\\Inovance Control\\\\InoProShop'
            '\\\\CODESYS\\\\Common\\\\InoProShop.exe",\n'
            '  "profile": "InoProShop(V1.9.1.6)"\n}'
        )

    # 创建临时文件
    tmpdir = tempfile.gettempdir()
    ts = "{}_{}".format(int(time.time() * 1000), os.getpid())
    script_file = os.path.join(tmpdir, "inopro_script_{}.py".format(ts))
    result_file = os.path.join(tmpdir, "inopro_result_{}.txt".format(ts))

    # live 模式：脚本执行完后不退出 InoProShop，保持 GUI 打开
    script_final = script_body
    if live:
        # 替换所有 sys.exit(0) → 写标记后等待（保持 InoProShop 存活）
        script_final = script_body.replace(
            "_sys.exit(0)", "rlog('SCRIPT_LIVE_DONE'); _sys.stdin.readline()"
        )
        # 也处理 sys.exit(1) → 写错误标记后等待
        script_final = script_final.replace(
            "_sys.exit(1)", "rlog('SCRIPT_LIVE_ERROR'); _sys.stdin.readline()"
        )

    # 组装完整脚本
    header = SCRIPT_HEADER.format(result_file.replace("\\", "\\\\"))
    full_script = header + script_final

    with open(script_file, "w", encoding="utf-8") as f:
        f.write(full_script)

    proc = None
    try:
        exe_dir = os.path.dirname(exe)
        env = os.environ.copy()
        env["PATH"] = "{};{}".format(exe_dir, env.get("PATH", ""))

        # live 模式：不捕获管道（避免阻塞 GUI）
        if live:
            proc = subprocess.Popen(
                [exe, "--profile={}".format(prof),
                 "--runscript={}".format(script_file)],
                cwd=exe_dir,
                env=env,
                # 不捕获输出，让 InoProShop 正常显示 GUI
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            proc = subprocess.Popen(
                [exe, "--profile={}".format(prof),
                 "--runscript={}".format(script_file)],
                cwd=exe_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        # 轮询结果文件
        start = time.time()
        timeout = 300
        done_marker = "SCRIPT_LIVE_DONE" if live else "SCRIPT_SUCCESS"
        error_markers = ["SCRIPT_LIVE_ERROR" if live else "SCRIPT_ERROR",
                         "SCRIPT_ERROR"]

        while time.time() - start < timeout:
            if not live and proc.poll() is not None:
                break
            try:
                with open(result_file, "r", encoding="utf-8",
                          errors="replace") as f:
                    content = f.read()
                if done_marker in content:
                    break
                if any(m in content for m in error_markers):
                    break
            except FileNotFoundError:
                pass
            time.sleep(1)

        output = ""
        try:
            with open(result_file, "r", encoding="utf-8", errors="replace") as f:
                output = f.read()
        except FileNotFoundError:
            output = "No output captured."

        # 非 live 模式：收集进程输出并杀进程
        if not live:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                stdout, stderr = proc.communicate(timeout=2)
                if stdout:
                    output += "\n" + stdout.decode("utf-8", errors="replace")
                if stderr:
                    output += "\n" + stderr.decode("utf-8", errors="replace")
            except Exception:
                pass

        if live:
            success = "SCRIPT_LIVE_DONE" in output
        else:
            success = "SCRIPT_SUCCESS" in output
        return success, output

    finally:
        # 清理临时脚本文件（结果文件保留到下次覆盖）
        for f in [script_file]:
            try:
                os.unlink(f)
            except Exception:
                pass
        # live 模式下不删结果文件太快
        if not live:
            for f in [result_file]:
                try:
                    os.unlink(f)
                except Exception:
                    pass


# ========== CLI 入口 ==========

def main():
    # 检测 --live 标志
    live = False
    args = sys.argv[1:]
    if "--live" in args:
        live = True
        args.remove("--live")

    if len(args) < 1:
        print("InoProShop CLI v{}".format(VERSION))
        print("用法: python inopro.py <命令> [参数...]")
        print()
        print("命令:")
        print("  open <工程路径>                  打开 .project 工程")
        print("  compile                          编译工程")
        print("  structure                        查看工程结构树")
        print("  create-pou <名> <类型> [语言]    创建 POU")
        print("  set-code <路径> <声明> <实现>    写入代码")
        print("  get-code <路径>                  读取代码")
        print("  create-task <名> [us] [优先级]   创建任务")
        print("  raw <代码>                       直接执行 IronPython")
        print("  config                           显示配置")
        print("  status                           检查状态")
        print()
        print("  --live                            实时模式，InoProShop 保持打开可见")
        print()
        print("跨电脑: 复制文件 + Python 3.7+ = 即插即用")
        return

    cmd = args[0]

    if cmd == "config":
        config = get_config()
        print("InoProShop EXE: {}".format(config["exe"]))
        print("Profile:        {}".format(config["profile"]))
        print("Exists:         {}".format(
            os.path.exists(config["exe"] or "") if config["exe"] else False
        ))
        return

    if cmd == "status":
        config = get_config()
        if config["exe"] and os.path.exists(config["exe"]):
            print("InoProShop found: {}".format(config["exe"]))
            success, output = run_ironpython("""
try:
    proj = script_engine.projects.primary
    rlog("Connected: " + str(proj.get_name() if proj else "No project open"))
    rlog("SCRIPT_SUCCESS")
except Exception as e:
    rlog("SCRIPT_ERROR: " + str(e))
""")
            for line in output.split("\n"):
                line = line.strip()
                if line and "SCRIPT_" not in line:
                    print(line)
        else:
            print("InoProShop not found!")
            print("set INOPRO_PATH=D:\\...\\InoProShop.exe")
        return

    # 执行命令
    success = False
    output = ""

    if live:
        print("🔴 LIVE 模式 — InoProShop 将保持打开，操作完成后可手动关闭")
        print()

    try:
        if cmd == "open" and len(args) >= 2:
            success, output = run_ironpython(script_open_project(args[1]), live=live)

        elif cmd == "compile":
            success, output = run_ironpython(script_compile(), live=live)

        elif cmd == "structure":
            success, output = run_ironpython(script_get_structure(), live=live)

        elif cmd == "create-pou" and len(args) >= 3:
            name = args[1]
            pou_type = args[2]
            lang = args[3] if len(args) > 3 else "st"
            parent = args[4] if len(args) > 4 else ""
            success, output = run_ironpython(
                script_create_pou(name, pou_type, lang, parent), live=live
            )

        elif cmd == "set-code" and len(args) >= 4:
            path = args[1]
            decl = args[2]
            impl = args[3]
            success, output = run_ironpython(
                script_set_pou_code(path, decl, impl), live=live
            )

        elif cmd == "get-code" and len(args) >= 2:
            success, output = run_ironpython(script_get_pou_code(args[1]), live=live)

        elif cmd == "create-task" and len(args) >= 2:
            name = args[1]
            interval = int(args[2]) if len(args) > 2 else 4000
            priority = int(args[3]) if len(args) > 3 else 1
            success, output = run_ironpython(
                script_create_task(name, interval, priority), live=live
            )

        elif cmd == "raw":
            code = " ".join(args[1:]) if len(args) > 1 else sys.stdin.read()
            success, output = run_ironpython(code, live=live)

        else:
            print("未知命令: {}".format(cmd))
            return

    except Exception as e:
        output = "Exception: {}".format(e)
        success = False

    # 输出结果（过滤标记行）
    for line in output.split("\n"):
        line = line.strip()
        if line and "SCRIPT_SUCCESS" not in line and "SCRIPT_ERROR" not in line \
           and "SCRIPT_LIVE_DONE" not in line and "SCRIPT_LIVE_ERROR" not in line:
            print(line)

    if success:
        print("\n✅ SUCCESS")
        if live:
            print("📌 InoProShop 仍保持打开，你可以在界面上查看/编辑。")
            print("   完成后手动关闭 InoProShop 即可。")
    else:
        print("\n❌ FAILED")


if __name__ == "__main__":
    main()
