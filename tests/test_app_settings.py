"""File > Recent (Stage: Recent Files list) is backed by app_settings'
recent_files list - these exercise add_recent_file/remove_recent_file
against a temp settings file rather than the user's real
~/.our-planner/settings.json.
"""

from src.utils import app_settings


def _use_tmp_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(app_settings, 'SETTINGS_PATH', tmp_path / 'settings.json')


def test_add_recent_file_moves_existing_entry_to_front(monkeypatch, tmp_path):
    _use_tmp_settings(monkeypatch, tmp_path)

    app_settings.add_recent_file('/a.json')
    app_settings.add_recent_file('/b.json')
    app_settings.add_recent_file('/a.json')

    assert app_settings.load_settings()['recent_files'] == ['/a.json', '/b.json']


def test_add_recent_file_caps_at_max_most_recent_first(monkeypatch, tmp_path):
    _use_tmp_settings(monkeypatch, tmp_path)

    for i in range(app_settings.MAX_RECENT_FILES + 2):
        app_settings.add_recent_file(f'/{i}.json')

    recent = app_settings.load_settings()['recent_files']
    assert len(recent) == app_settings.MAX_RECENT_FILES
    assert recent[0] == f'/{app_settings.MAX_RECENT_FILES + 1}.json'


def test_remove_recent_file(monkeypatch, tmp_path):
    _use_tmp_settings(monkeypatch, tmp_path)

    app_settings.add_recent_file('/a.json')
    app_settings.add_recent_file('/b.json')
    app_settings.remove_recent_file('/a.json')

    assert app_settings.load_settings()['recent_files'] == ['/b.json']


def test_remove_recent_file_missing_entry_is_a_noop(monkeypatch, tmp_path):
    _use_tmp_settings(monkeypatch, tmp_path)

    app_settings.add_recent_file('/a.json')
    app_settings.remove_recent_file('/not-listed.json')

    assert app_settings.load_settings()['recent_files'] == ['/a.json']


def test_recent_files_defaults_to_empty_list(monkeypatch, tmp_path):
    _use_tmp_settings(monkeypatch, tmp_path)

    assert app_settings.load_settings()['recent_files'] == []
