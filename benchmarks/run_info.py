"""Commit, corpus, and hardware details recorded with each benchmark run."""

import platform
import subprocess
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]


def git_state():
    """HEAD at run time and whether tracked or untracked files differed from it."""
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    return {"git_head_at_run": head, "worktree_clean": not status.strip()}


def describe_git(result):
    """Markdown line naming the measured commit and worktree state."""
    clean = result.get("worktree_clean")
    state = "clean worktree" if clean else "worktree changes may have been present" if clean is None else "uncommitted worktree changes present"
    return f"Git HEAD at run: `{result['git_head_at_run']}` ({state})."


def corpus_size(db=None):
    """PDF page counts from data/ and the number of chunks stored in Chroma."""
    files = {path.name: len(PdfReader(str(path)).pages) for path in sorted((ROOT / "data").glob("*.pdf"))}
    if db is None:
        from app.engine import get_vector_db
        db = get_vector_db()
    return {"files": files, "pages": sum(files.values()), "chunks": len(db.get(include=[])["ids"])}


def host_hardware():
    """GPU name and memory (when nvidia-smi is available), CPU, and OS of the benchmark host."""
    try:
        gpu = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], text=True, timeout=10
        ).strip() or None
    except (OSError, subprocess.SubprocessError):
        gpu = None
    cpu = platform.processor() or platform.machine()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    except (ImportError, OSError):
        pass
    return {"gpu": gpu, "cpu": cpu, "os": platform.platform()}
