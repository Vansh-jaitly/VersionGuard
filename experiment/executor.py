"""Run a program in the task's pinned environment.

DockerExecutor (default for real runs)
    One image per environment: python:<version>-slim plus the pinned
    libraries. Programs run with no network, a memory limit, a read-only file
    system and a time limit, because they are written by a model. Images are
    built for linux/amd64 on every laptop (including Apple Silicon) so both
    laptops test against identical environments.

HostExecutor (self-check and CI only)
    Runs with the current Python. It does NOT pin versions and does NOT
    sandbox, so it is only for the made-up fixture library and for trusted
    code. For fixture tasks it puts experiment/fixtures/libs/<lib>-<version>
    on the import path, which is how the two minilib versions are "installed".
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from experiment.dataset import FIXTURE_LIBS
from versionguard.config import REPO_ROOT, settings
from versionguard.task import Task

PROGRAM_NAME = "prog.py"
WORK_ROOT = REPO_ROOT / ".vg_work"  # inside the repo so Docker Desktop can always mount it
APIDOCS_SCRIPT = REPO_ROOT / "versionguard" / "apidocs.py"
IMAGE_PREFIX = "versionguard-env"
PLATFORM = "linux/amd64"
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]


def docker_executable() -> Optional[str]:
    """Resolve Docker when the desktop app started before PATH was updated."""
    configured = os.getenv("VG_DOCKER_EXE")
    if configured and Path(configured).is_file():
        return configured
    found = shutil.which("docker")
    if found:
        return found
    if os.name == "nt":
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        for candidate in (
            program_files / "Docker" / "Docker" / "resources" / "bin" / "docker.exe",
            program_files / "Docker" / "Docker" / "resources" / "cli-plugins" / "docker.exe",
        ):
            if candidate.is_file():
                return str(candidate)
    return None


class EnvFailure(RuntimeError):
    """The pinned environment could not be built or used (not the model's fault)."""


@dataclass
class ExecResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_ms: float = 0.0


def _run(command: list[str], timeout: Optional[float] = None, env: Optional[dict] = None, cwd=None):
    return subprocess.run(  # noqa: S603 - argument list, no shell
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
        cwd=cwd,
        check=False,
        creationflags=_NO_WINDOW,
    )


def build_error_summary(log: str, limit: int = 6) -> str:
    """The lines of a docker build log that say what went wrong (pip's own errors first)."""
    lines = [line.strip() for line in log.splitlines() if line.strip()]
    lines = [line.split(" ", 2)[-1] if line.startswith("#") else line for line in lines]  # drop "#7 12.3 "
    wanted = [line for line in lines if "error" in line.lower() or "no matching distribution" in line.lower()]
    picked = wanted[:limit] if wanted else lines[-limit:]
    return "\n".join(line[:240] for line in picked)


class _WorkDir:
    """A scratch folder for one execution, removed afterwards."""

    def __init__(self) -> None:
        self.path = WORK_ROOT / uuid.uuid4().hex[:12]

    def __enter__(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=False)
        return self.path

    def __exit__(self, *_exc) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


def fixture_lib_dir(task: Task) -> Optional[Path]:
    path = FIXTURE_LIBS / f"{task.library}-{task.version}"
    return path if path.is_dir() else None


class HostExecutor:
    name = "host"

    def __init__(self, python: Optional[str] = None) -> None:
        self.python = python or sys.executable

    def _env(self, task: Task) -> dict:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        lib_dir = fixture_lib_dir(task)
        if lib_dir is not None:
            env["PYTHONPATH"] = str(lib_dir)
        else:
            env.pop("PYTHONPATH", None)
        return env

    def ensure(self, task: Task) -> None:
        return None

    def run(self, task: Task, source: str, timeout: Optional[int] = None) -> ExecResult:
        timeout = timeout or settings.exec_timeout_s
        with _WorkDir() as work:
            (work / PROGRAM_NAME).write_text(source, encoding="utf-8")
            start = time.perf_counter()
            try:
                done = _run([self.python, "-s", PROGRAM_NAME], timeout=timeout, env=self._env(task), cwd=work)
            except subprocess.TimeoutExpired:
                return ExecResult(-1, "", "", True, (time.perf_counter() - start) * 1000)
            return ExecResult(done.returncode, done.stdout, done.stderr, False, (time.perf_counter() - start) * 1000)

    def extract_docs(self, task: Task, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        command = [self.python, "-s", str(APIDOCS_SCRIPT), "--out", str(out_path)]
        if fixture_lib_dir(task) is not None:
            command += ["--module", task.library]
        else:
            for dist in task.distributions:
                command += ["--dist", dist]
        done = _run(command, timeout=600, env=self._env(task))
        if done.returncode != 0 or not out_path.is_file():
            raise EnvFailure(f"documentation extraction failed: {done.stderr.strip()[-400:]}")


class DockerExecutor:
    name = "docker"

    def __init__(self, memory: str = "2g", cpus: str = "2") -> None:
        self.memory = memory
        self.cpus = cpus
        self._ready: set[str] = set()
        self.docker = docker_executable() or "docker"

    @staticmethod
    def available() -> tuple[bool, str]:
        docker = docker_executable()
        if docker is None:
            return False, "docker executable was not found (set VG_DOCKER_EXE if needed)"
        try:
            done = _run([docker, "info", "--format", "{{.ServerVersion}}"], timeout=30)
        except subprocess.TimeoutExpired:
            return False, "docker did not answer (is Docker Desktop running?)"
        if done.returncode != 0:
            return False, (done.stderr.strip().splitlines() or ["docker daemon not reachable"])[-1]
        return True, done.stdout.strip()

    def image(self, task: Task) -> str:
        return f"{IMAGE_PREFIX}:{task.env_key}"

    def dockerfile(self, task: Task) -> str:
        import json

        # Exec form (a JSON array): requirement strings never pass through a shell.
        install = ["python", "-m", "pip", "install", "--no-cache-dir", *task.requirements, "pytest"]
        return (
            f"FROM python:{task.python_version}-slim\n"
            "ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1\n"
            f"RUN {json.dumps(install)}\n"
        )

    def ensure(self, task: Task) -> None:
        tag = self.image(task)
        if tag in self._ready:
            return
        if _run([self.docker, "image", "inspect", tag], timeout=60).returncode != 0:
            with _WorkDir() as work:
                (work / "Dockerfile").write_text(self.dockerfile(task), encoding="utf-8")
                try:
                    done = _run(
                        [self.docker, "build", "--progress", "plain", "--platform", PLATFORM, "-t", tag, str(work)],
                        timeout=3600,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise EnvFailure(f"building {tag} timed out") from exc
            if done.returncode != 0:
                raise EnvFailure(f"could not build {tag}:\n{build_error_summary(done.stderr or done.stdout)}")
        self._ready.add(tag)

    def _base_command(self, name: str) -> list[str]:
        return [
            self.docker, "run", "--rm", "--name", name,
            "--platform", PLATFORM,
            "--network", "none",
            "--memory", self.memory, "--cpus", self.cpus, "--pids-limit", "256",
            "--read-only", "--tmpfs", "/tmp:rw,exec,size=512m",
            "-e", "HOME=/tmp", "-e", "MPLCONFIGDIR=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-e", "PYTHONIOENCODING=utf-8",
            "-w", "/tmp",
        ]  # fmt: skip

    def run(self, task: Task, source: str, timeout: Optional[int] = None) -> ExecResult:
        timeout = timeout or settings.exec_timeout_s
        self.ensure(task)
        name = f"vg-{uuid.uuid4().hex[:12]}"
        with _WorkDir() as work:
            (work / PROGRAM_NAME).write_text(source, encoding="utf-8")
            command = self._base_command(name) + [
                "--mount", f"type=bind,source={work},target=/work,readonly",
                self.image(task), "python", f"/work/{PROGRAM_NAME}",
            ]  # fmt: skip
            start = time.perf_counter()
            try:
                # Extra seconds cover container start-up, which is not the program's time.
                done = _run(command, timeout=timeout + 20)
            except subprocess.TimeoutExpired:
                _run([self.docker, "kill", name], timeout=30)
                return ExecResult(-1, "", "", True, (time.perf_counter() - start) * 1000)
            duration = (time.perf_counter() - start) * 1000
        if done.returncode == 125 or "Unable to find image" in done.stderr:
            raise EnvFailure(f"docker could not start the container: {done.stderr.strip()[-300:]}")
        return ExecResult(done.returncode, done.stdout, done.stderr, False, duration)

    def extract_docs(self, task: Task, out_path: Path) -> None:
        self.ensure(task)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        name = f"vg-docs-{uuid.uuid4().hex[:12]}"
        with _WorkDir() as work:
            shutil.copy(APIDOCS_SCRIPT, work / "apidocs.py")
            command = self._base_command(name) + [
                "--mount", f"type=bind,source={work},target=/work",
                self.image(task), "python", "/work/apidocs.py", "--out", "/work/apidocs.jsonl",
            ]  # fmt: skip
            for dist in task.distributions:
                command += ["--dist", dist]
            try:
                done = _run(command, timeout=900)
            except subprocess.TimeoutExpired as exc:
                _run([self.docker, "kill", name], timeout=30)
                raise EnvFailure("documentation extraction timed out") from exc
            produced = work / "apidocs.jsonl"
            if done.returncode != 0 or not produced.is_file():
                raise EnvFailure(f"documentation extraction failed: {done.stderr.strip()[-400:]}")
            shutil.copy(produced, out_path)


def make_executor(kind: str):
    if kind == "host":
        return HostExecutor()
    if kind == "docker":
        return DockerExecutor()
    raise ValueError(f"Unknown executor '{kind}' (use docker or host)")
