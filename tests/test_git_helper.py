"""git_helper wraps plain `git` subprocess calls for versioned project
folders - these exercise it against a real, throwaway repo under tmp_path
rather than mocking subprocess, since the whole point is to prove the
actual git invocations do what version_control_operations.py will rely on
(e.g. that checkout_file_content never moves HEAD).
"""

import subprocess

import pytest

from src.utils import git_helper


@pytest.fixture
def repo(tmp_path):
    """An initialized repo with a configured identity (git_helper itself
    checks for this via is_git_configured, so tests need it set to get
    past that) and one tracked file."""
    git_helper.init_repo(tmp_path)
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True
    )
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True
    )
    (tmp_path / 'project.json').write_text('{"v": 1}')
    git_helper.add(tmp_path, ['project.json'])
    git_helper.commit(tmp_path, 'Initial commit')
    return tmp_path


def test_is_git_available():
    assert git_helper.is_git_available() is True


def test_is_git_configured_true_when_identity_set(repo):
    assert git_helper.is_git_configured(repo) is True


def test_is_git_configured_false_without_identity(tmp_path, monkeypatch):
    # Point HOME at an empty directory so no global ~/.gitconfig identity
    # leaks into the check - without this, a real developer machine (which
    # always has one) would make this test pass for the wrong reason.
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setenv('HOME', str(fake_home))
    monkeypatch.delenv('GIT_AUTHOR_NAME', raising=False)
    monkeypatch.delenv('GIT_AUTHOR_EMAIL', raising=False)
    monkeypatch.delenv('GIT_COMMITTER_NAME', raising=False)
    monkeypatch.delenv('GIT_COMMITTER_EMAIL', raising=False)

    repo_dir = tmp_path / 'repo'
    repo_dir.mkdir()
    git_helper.init_repo(repo_dir)

    assert git_helper.is_git_configured(repo_dir) is False


def test_init_repo_defaults_to_main_branch(tmp_path):
    git_helper.init_repo(tmp_path)
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'], cwd=tmp_path, check=True
    )
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True
    )
    (tmp_path / 'f.txt').write_text('x')
    git_helper.add(tmp_path, ['f.txt'])
    git_helper.commit(tmp_path, 'first')
    assert git_helper.current_branch(tmp_path) == 'main'


def test_commit_creates_a_new_log_entry(repo):
    (repo / 'project.json').write_text('{"v": 2}')
    git_helper.add(repo, ['project.json'])
    git_helper.commit(repo, 'Second commit')

    commits = git_helper.log(repo, 'main')
    assert [c.message for c in commits] == ['Second commit', 'Initial commit']


def test_create_branch_and_checkout(repo):
    git_helper.create_branch(repo, 'autosave')
    git_helper.checkout(repo, 'autosave')
    assert git_helper.current_branch(repo) == 'autosave'


def test_checkout_file_content_reads_historical_blob_without_moving_head(repo):
    first_sha = git_helper.log(repo, 'main')[0].sha

    (repo / 'project.json').write_text('{"v": 2}')
    git_helper.add(repo, ['project.json'])
    git_helper.commit(repo, 'Second commit')

    old_content = git_helper.checkout_file_content(repo, first_sha, 'project.json')
    assert old_content == b'{"v": 1}'
    # HEAD must not have moved - checkout_file_content only reads a blob
    assert git_helper.current_branch(repo) == 'main'
    assert (repo / 'project.json').read_text() == '{"v": 2}'


def test_merge_squash_then_reset_branch_collapses_autosave_onto_main(repo):
    git_helper.create_branch(repo, 'autosave')
    git_helper.checkout(repo, 'autosave')

    for i in range(2, 4):
        (repo / 'project.json').write_text(f'{{"v": {i}}}')
        git_helper.add(repo, ['project.json'])
        git_helper.commit(repo, f'Autosave {i}')

    git_helper.checkout(repo, 'main')
    git_helper.merge_squash(repo, 'autosave')
    git_helper.commit(repo, 'Checkpoint')
    git_helper.reset_branch(repo, 'autosave', 'main')
    git_helper.checkout(repo, 'autosave')

    main_commits = git_helper.log(repo, 'main')
    assert [c.message for c in main_commits] == ['Checkpoint', 'Initial commit']
    autosave_commits = git_helper.log(repo, 'autosave')
    assert [c.message for c in autosave_commits] == ['Checkpoint', 'Initial commit']
    assert git_helper.current_branch(repo) == 'autosave'
    assert git_helper.is_clean(repo)


def test_merge_abort_unwinds_a_conflicting_squash(repo):
    git_helper.create_branch(repo, 'autosave')
    git_helper.checkout(repo, 'autosave')
    (repo / 'project.json').write_text('{"v": "autosave"}')
    git_helper.add(repo, ['project.json'])
    git_helper.commit(repo, 'Autosave change')

    git_helper.checkout(repo, 'main')
    (repo / 'project.json').write_text('{"v": "main"}')
    git_helper.add(repo, ['project.json'])
    git_helper.commit(repo, 'Conflicting main change')

    with pytest.raises(git_helper.GitError):
        git_helper.merge_squash(repo, 'autosave')

    git_helper.merge_abort(repo)
    assert git_helper.is_clean(repo)
    assert git_helper.current_branch(repo) == 'main'


def test_is_clean_false_with_unstaged_changes(repo):
    (repo / 'project.json').write_text('{"v": 2}')
    assert git_helper.is_clean(repo) is False


def test_commit_raises_git_error_when_nothing_staged(repo):
    with pytest.raises(git_helper.GitError):
        git_helper.commit(repo, 'Nothing to commit')


def test_reset_branch_refuses_the_current_branch(repo):
    """git itself refuses `branch -f` on the checked-out branch (confirmed
    live) - reset_hard exists specifically for that case instead."""
    first_sha = git_helper.log(repo, 'main')[0].sha
    with pytest.raises(git_helper.GitError):
        git_helper.reset_branch(repo, 'main', first_sha)


def test_reset_hard_moves_the_current_branch_and_working_tree(repo):
    first_sha = git_helper.log(repo, 'main')[0].sha
    (repo / 'project.json').write_text('{"v": 2}')
    git_helper.add(repo, ['project.json'])
    git_helper.commit(repo, 'Second commit')

    git_helper.reset_hard(repo, first_sha)

    assert git_helper.log(repo, 'main')[0].sha == first_sha
    assert (repo / 'project.json').read_text() == '{"v": 1}'
    assert git_helper.is_clean(repo)
    assert git_helper.current_branch(repo) == 'main'
