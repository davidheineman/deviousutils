import os
import hashlib
import random
import subprocess
import shlex
from pathlib import Path
from yaspin import yaspin

ALLOWED_TOOLS = [
    "Bash",
    "Edit",
    "Write",
    "Read",
    "Glob",
    "Grep",
    "LS",
    "WebFetch",
    "NotebookEdit",
    "NotebookRead",
    "TodoRead",
    "TodoWrite",
    "Agent",
]


def create_cache_dir():
    # Create random hash
    task_hash = hashlib.md5(str(random.random()).encode()).hexdigest()

    # Create cache directory
    cache_dir = Path.home() / ".cache" / "deviousutils" / task_hash
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create rollout subfolder
    rollout_dir = cache_dir / "rollout"
    rollout_dir.mkdir(parents=True, exist_ok=True)

    return cache_dir


def run_claude_with_cache(
    instruction: str,
    model_name: str = "claude-sonnet-4-20250514",
    cache_dir=None,
    verbose=False,
    show_spinner=False,
    working_dir=None,
):
    # Set the model
    os.environ["ANTHROPIC_MODEL"] = model_name
    os.environ["FORCE_AUTO_BACKGROUND_TASKS"] = "1"
    os.environ["ENABLE_BACKGROUND_TASKS"] = "1"

    if cache_dir is None:
        cache_dir = create_cache_dir()

    # Resolve target directory
    original_cwd = Path.cwd()
    rollout_dir = cache_dir / "rollout"
    rollout_dir.mkdir(parents=True, exist_ok=True)
    target_dir = Path(working_dir) if working_dir is not None else rollout_dir
    if working_dir is None:
        os.chdir(rollout_dir)

    spinner = None
    if show_spinner:
        spinner = yaspin(text=f"{instruction.split('\n')[0][:50]}...", color="cyan")
        spinner.start()

    try:
        # Escape the instruction for shell
        escaped_instruction = shlex.quote(instruction)

        # Build and run the claude command
        argv = [
            "claude",
            "--verbose",
            "--output-format",
            "stream-json",
            "-p",
            escaped_instruction,
            "--allowedTools",
            *ALLOWED_TOOLS,
            # "--permission-prompt-tool", "auto",
        ]

        # Minimal env to discourage TTY features
        env = {**os.environ, "CI": "1", "TERM": "dumb"}

        process = subprocess.Popen(
            argv,
            shell=False,
            cwd=str(target_dir),
            stdin=subprocess.DEVNULL,  # <-- prevents EBADF on fd 0
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=env,
        )

        output_lines = []
        error_lines = []

        # Read stdout and stderr separately
        import threading

        def read_stdout():
            for line in process.stdout:
                # Print output in real-time
                if verbose:
                    print(line, end="")
                output_lines.append(line)

        def read_stderr():
            for line in process.stderr:
                error_lines.append(line)

        stdout_thread = threading.Thread(target=read_stdout)
        stderr_thread = threading.Thread(target=read_stderr)

        stdout_thread.start()
        stderr_thread.start()

        stdout_thread.join()
        stderr_thread.join()

        process.wait()

        class Result:
            def __init__(self, returncode, stdout, stderr):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        result = Result(process.returncode, "".join(output_lines), "".join(error_lines))

        if result.returncode != 0:
            raise RuntimeError(
                f"claude failed with return code {result.returncode}. stderr: {result.stderr}"
            )

        if spinner:
            spinner.ok("done!")

        # Save result to cache directory
        result_path = cache_dir / "stdout.jsonl"
        with open(result_path, "w") as f:
            f.write(result.stdout)

        # Save stderr to cache directory
        stderr_path = cache_dir / "stderr.out"
        with open(stderr_path, "w") as f:
            f.write(result.stderr)

        return result, cache_dir
    except Exception as e:
        if spinner:
            spinner.fail("fail")
        raise
    finally:
        if working_dir is None:
            os.chdir(original_cwd)
