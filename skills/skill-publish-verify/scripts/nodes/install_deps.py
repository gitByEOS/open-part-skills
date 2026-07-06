"""install_deps 节点:venv 里按 requirements.txt 或 SKILL.md frontmatter 装依赖。

优先级:
1. skill/requirements.txt 存在 → pip install -r(整批一次)
2. 否则解析 frontmatter dependencies,逐个 pip install

pip 全文(stdout+stderr)写 work_dir/install_deps.log 供审计。
对 frontmatter dep 跑 pip 找不到发行版的判为系统二进制(ffmpeg/python3)记 skipped。
依赖漏写不在本节点暴露,而在 agent_run 跑 skill 时 ModuleNotFoundError 暴露——
这正是黑盒要测的环节。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from esflow import Node

from common import INSTALL_DEPS_LOG, log


def parse_skill_dependencies(skill_md_text):
    """极简 frontmatter 解析:取 dependencies 列表,不引 PyYAML。"""
    lines = skill_md_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    deps = []
    in_deps = False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("dependencies:"):
            in_deps = True
            continue
        if in_deps:
            stripped = line.strip()
            if stripped.startswith("- "):
                deps.append(stripped[2:].strip())
            elif stripped and not line.startswith((" ", "\t")):
                in_deps = False
    return deps


def pip_install(python, args, log_path: Path):
    """venv 里装一批依赖,合并写日志,返回 (returncode, stdout, stderr)。"""
    cmd = [str(python), "-m", "pip", "install", "--disable-pip-version-check", *args]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"$ {' '.join(cmd)}\n")
        f.write(f"[returncode={result.returncode}]\n")
        f.write(result.stdout)
        if result.stderr:
            f.write(result.stderr)
        f.write("\n")
    return result


class InstallDeps(Node):
    id = "install_deps"
    title = "装 skill 依赖"

    def run(self, ctx) -> dict:
        isolate = ctx.get("isolate_env")
        copy_skill = ctx.get("copy_skill")
        python = Path(isolate["python"])
        work_dir = Path(isolate["work_dir"])
        skill_dir = Path(copy_skill["skill_dir"])
        skill_md = skill_dir / "SKILL.md"
        log_path = work_dir / INSTALL_DEPS_LOG
        log_path.write_text("", encoding="utf-8")  # 清空旧日志

        req_file = skill_dir / "requirements.txt"
        installed, skipped = [], []

        if req_file.is_file():
            result = pip_install(python, ["-r", str(req_file)], log_path)
            if result.returncode == 0:
                installed.append(f"-r {req_file.name}")
                log(f"[install_deps] + -r {req_file.name}")
            else:
                # -r 整批失败按整批记 skipped,细节在 log
                skipped.append({"dep": f"-r {req_file.name}", "reason": "pip_install_failed"})
                log(f"[install_deps] - -r {req_file.name} (pip install 失败,见 log)")
        else:
            deps = parse_skill_dependencies(skill_md.read_text(encoding="utf-8"))
            for dep in deps:
                result = pip_install(python, [dep], log_path)
                stderr = result.stderr.strip()
                if result.returncode == 0:
                    installed.append(dep)
                    log(f"[install_deps] + {dep}")
                elif "No matching distribution" in stderr or "Could not find a version" in stderr:
                    skipped.append({"dep": dep, "reason": "not_a_pip_package"})
                    log(f"[install_deps] - {dep} (not_a_pip_package)")
                else:
                    skipped.append({"dep": dep, "reason": stderr.splitlines()[-1] if stderr else "pip install failed"})
                    log(f"[install_deps] - {dep} (failed,见 log)")

        return {
            "installed": installed,
            "skipped": skipped,
            "log_path": str(log_path),
            "source": "requirements.txt" if req_file.is_file() else "frontmatter",
        }

    def deliver(self, artifact) -> bool:
        return bool(artifact and "installed" in artifact and artifact.get("log_path"))
