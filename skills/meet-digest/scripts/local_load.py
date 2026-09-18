"""读 scripts/local.py。必须在 import esflow 之前可用。"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

from common import EXIT_VALIDATION, CliError, log

LOCAL_NAME = "local.py"
KEYS = ("PYTHON", "FFMPEG", "DOWNLOAD_ROOT", "MODEL", "DEVICE", "COMPUTE_TYPE")


def local_path() -> Path:
    return Path(__file__).resolve().parent / LOCAL_NAME


def load_local() -> dict[str, str]:
    path = local_path()
    data = {key: "" for key in KEYS}
    if not path.is_file():
        return data
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        raise CliError("runtime_invalid", f"local.py 语法错误:{exc}", EXIT_VALIDATION)
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id not in data:
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(
            node.value.value, str
        ):
            raise CliError(
                "runtime_invalid",
                f"local.py 的 {target.id} 必须是字符串字面量",
                EXIT_VALIDATION,
            )
        data[target.id] = node.value.value.strip()
    return data


def runtime_cfg() -> dict[str, str]:
    data = load_local()
    return {
        "ffmpeg": data["FFMPEG"],
        "download_root": data["DOWNLOAD_ROOT"],
        "model": data["MODEL"],
        "device": data["DEVICE"],
        "compute_type": data["COMPUTE_TYPE"],
    }


def _is_current_python(target: Path) -> bool:
    if target.parent.name == "bin":
        venv_root = target.parent.parent
        if Path(sys.prefix).resolve() == venv_root.resolve():
            return True
    try:
        return os.path.samefile(sys.executable, target)
    except OSError:
        return False


def hop_to_local_python() -> None:
    """有 PYTHON 且不是当前解释器则切过去。必须在 import esflow 之前调用。"""
    try:
        python = load_local()["PYTHON"]
    except CliError as error:
        log(error.message)
        sys.exit(error.exit_code)
    if not python:
        return
    target = Path(python).expanduser()
    if not target.is_file():
        log(f"local.py PYTHON 不是文件:{target}")
        sys.exit(EXIT_VALIDATION)
    if _is_current_python(target):
        return
    log(f"切换解释器 {sys.executable} → {target}")
    script = str(Path(__file__).resolve().parent / "run.py")
    try:
        os.execv(str(target), [str(target), script, *sys.argv[1:]])
    except OSError as exc:
        log(f"无法切换到 {target}:{exc}")
        sys.exit(EXIT_VALIDATION)
