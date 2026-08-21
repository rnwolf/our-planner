"""Thin subprocess wrapper around git, for versioned project folders.

A versioned project folder is a directory the user deliberately turns into
a real git repo (see version_control_operations.py) - this module only
shells out to `git` and reports what happened; it knows nothing about the
app's own model, autosave policy, or branch strategy. A git failure here
must reach the user rather than being swallowed - unlike the xrandr probe
in ui_components.py (which degrades silently because monitor geometry is
a nice-to-have), a failed commit means an edit wasn't actually saved into
history, which the user needs to know about.
"""

import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple, Optional

TIMEOUT_SECONDS = 10


class GitError(Exception):
    """A git command exited non-zero (or couldn't be run at all) - carries
    the command's own stderr so the caller can show the user something
    more useful than a bare non-zero-exit message."""


class CommitInfo(NamedTuple):
    sha: str
    timestamp: str  # ISO 8601 author date
    message: str


def _run(
    path: Path, args: list[str], check: bool = True
) -> subprocess.CompletedProcess:
    """Runs `git <args>` in `path`. Raises GitError on a non-zero exit when
    check is True (the default); check=False is for calls whose exit code
    is itself meaningful rather than a failure (e.g. `config` lookups,
    `diff --cached --quiet`) - those callers inspect returncode themselves."""
    try:
        result = subprocess.run(
            ['git', *args],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise GitError(f'git {" ".join(args)} failed to run: {e}') from e
    if check and result.returncode != 0:
        raise GitError(f'git {" ".join(args)} failed: {result.stderr.strip()}')
    return result


def is_git_available() -> bool:
    """Whether the `git` binary is on PATH at all."""
    return shutil.which('git') is not None


def is_git_configured(path: Path) -> bool:
    """Whether git has a usable user.name/user.email for `path` (global or
    repo-local) - checked once before the first commit is attempted, since
    an unconfigured git fails every commit with no useful message of its
    own to show the user."""
    name = _run(path, ['config', 'user.name'], check=False).stdout.strip()
    email = _run(path, ['config', 'user.email'], check=False).stdout.strip()
    return bool(name) and bool(email)


def init_repo(path: Path) -> None:
    """Initializes a new repo at `path` with `main` as the default branch.
    `-b main` needs git >= 2.28 (released 2020) - not hedged against older
    git here, since anything currently receiving security updates ships
    well past that."""
    _run(path, ['init', '-b', 'main'])


def add(path: Path, files: list[str]) -> None:
    _run(path, ['add', *files])


def commit(path: Path, message: str) -> None:
    _run(path, ['commit', '-m', message])


def create_branch(path: Path, name: str, at: Optional[str] = None) -> None:
    args = ['branch', name]
    if at is not None:
        args.append(at)
    _run(path, args)


def checkout(path: Path, ref: str) -> None:
    _run(path, ['checkout', ref])


def checkout_file_content(path: Path, ref: str, file: str) -> bytes:
    """The content of `file` as it was at `ref`, without touching HEAD or
    the working tree - `git show` reads a historical blob directly, unlike
    `git checkout <ref>` which would detach HEAD (undo/redo must never do
    that - see version_control_operations.py's safety invariants)."""
    result = subprocess.run(
        ['git', 'show', f'{ref}:{file}'],
        cwd=path,
        capture_output=True,
        timeout=TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors='replace').strip()
        raise GitError(f'git show {ref}:{file} failed: {stderr}')
    return result.stdout


def merge_squash(path: Path, branch: str) -> None:
    _run(path, ['merge', '--squash', branch])


def merge_abort(path: Path) -> None:
    """Unwinds a failed merge_squash. `git merge --abort` relies on
    MERGE_HEAD, but `git merge --squash` never writes one (squash merges
    never become a real merge commit, by design) - confirmed live that
    `--abort` fails with "There is no merge to abort" on exactly the
    conflict this exists to clean up. `git reset --merge` is the call that
    actually clears a squash merge's conflicted index/working tree."""
    _run(path, ['reset', '--merge'])


def reset_branch(path: Path, branch: str, to_ref: str) -> None:
    """Force-moves `branch`'s tip to `to_ref` without checking it out -
    used to collapse autosave back onto main's new tip after a squash.
    Only valid for a branch OTHER than the one currently checked out - git
    refuses this on the current branch (confirmed live: "cannot force
    update the branch ... used by worktree"); use reset_hard for that
    case instead."""
    _run(path, ['branch', '-f', branch, to_ref])


def reset_hard(path: Path, ref: str) -> None:
    """Moves the CURRENTLY CHECKED OUT branch to `ref` and overwrites the
    working tree/index to match - the counterpart to reset_branch for the
    one case it can't handle. Used to discard autosave's redo-able future
    when a genuine new edit happens after the user has undone past it."""
    _run(path, ['reset', '--hard', ref])


def log(path: Path, branch: str) -> list[CommitInfo]:
    """Every commit on `branch`, most-recent first."""
    result = _run(path, ['log', branch, '--format=%H%x1f%aI%x1f%s'])
    commits = []
    for line in result.stdout.splitlines():
        sha, timestamp, message = line.split('\x1f', 2)
        commits.append(CommitInfo(sha, timestamp, message))
    return commits


def current_branch(path: Path) -> Optional[str]:
    """The branch HEAD is on, or None if HEAD is detached - callers use
    this as a sanity check that a git operation never left HEAD detached."""
    result = _run(path, ['symbolic-ref', '--short', '-q', 'HEAD'], check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def is_clean(path: Path) -> bool:
    return _run(path, ['status', '--porcelain']).stdout.strip() == ''
