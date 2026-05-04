#!/usr/bin/env python3
"""Download arXiv TeX source and open it in Claude Code."""

import argparse
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path


ARXIV_EPRINT_URL = "https://arxiv.org/e-print/{arxiv_id}"
CACHE_DIR = Path.home() / ".cache" / "arxiv"

SYSTEM_PROMPT = """
This directory contains the LaTeX source for arXiv paper {arxiv_id}. 
The .tex files are:

{tex_list}

You are a research assistant for this paper. Read the TeX source to 
answer questions — summarize findings, explain methods, clarify 
notation, compare with related work, etc.
"""


def download_source(arxiv_id: str, dest_dir: Path) -> None:
    url = ARXIV_EPRINT_URL.format(arxiv_id=arxiv_id)
    tarball = dest_dir / "source.tar.gz"

    print(f"Downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "arxiv-claude/0.1"})
    with urllib.request.urlopen(req) as resp, open(tarball, "wb") as f:
        shutil.copyfileobj(resp, f)

    if tarfile.is_tarfile(tarball):
        with tarfile.open(tarball) as tf:
            tf.extractall(dest_dir)
        tarball.unlink()
    else:
        tarball.rename(dest_dir / "main.tex")


def main():
    parser = argparse.ArgumentParser(description="view arxiv papers in Claude code")
    parser.add_argument("arxiv_id", help="e.g. 2605.00347v1")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    arxiv_id = args.arxiv_id.strip()

    if shutil.which("claude") is None:
        print("Error: `claude` CLI not found in PATH", file=sys.stderr)
        sys.exit(1)

    work_dir = CACHE_DIR / arxiv_id
    already_cached = work_dir.exists() and any(work_dir.iterdir())

    if args.refresh and work_dir.exists():
        shutil.rmtree(work_dir)
        already_cached = False

    work_dir.mkdir(parents=True, exist_ok=True)

    if not already_cached:
        try:
            download_source(arxiv_id, work_dir)
        except urllib.error.HTTPError as e:
            print(f"Error downloading source: {e}", file=sys.stderr)
            sys.exit(1)

    tex_files = list(work_dir.rglob("*.tex"))

    tex_list = "\n".join(str(f.relative_to(work_dir)) for f in tex_files)
    system_prompt = SYSTEM_PROMPT.format(arxiv_id=arxiv_id, tex_list=tex_list)

    print(f"Launching Claude Code in {work_dir} ...")
    subprocess.run(
        [
            "claude",
            "--append-system-prompt", system_prompt,
            "--dangerously-skip-permissions",
        ],
        cwd=work_dir,
    )


if __name__ == "__main__":
    main()
