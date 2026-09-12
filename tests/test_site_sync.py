from tools import sync_sites


def test_generated_site_files_are_current():
    assert sync_sites.sync_sites(check=True) == ()


def test_sync_reports_and_repairs_drift(tmp_path):
    root = tmp_path / "repository"
    changed = sync_sites.sync_sites(root)
    assert changed
    assert sync_sites.sync_sites(root, check=True) == ()

    task = root / "qinglong" / "DefaultTasks" / "checkin_task_javbus.py"
    task.write_text("changed", encoding="utf-8")
    assert task in sync_sites.sync_sites(root, check=True)
    assert task in sync_sites.sync_sites(root)
    assert sync_sites.GENERATED_MARKER in task.read_text(encoding="utf-8")


def test_sync_only_removes_stale_generated_tasks(tmp_path):
    task_dir = tmp_path / "qinglong" / "DefaultTasks"
    task_dir.mkdir(parents=True)
    stale = task_dir / "checkin_task_removed.py"
    custom = task_dir / "checkin_task_custom.py"
    stale.write_text(sync_sites.GENERATED_MARKER, encoding="utf-8")
    custom.write_text("# maintained manually", encoding="utf-8")

    sync_sites.sync_sites(tmp_path)

    assert not stale.exists()
    assert custom.exists()


def test_check_mode_does_not_write(tmp_path):
    expected = tmp_path / "qinglong" / "checkin-tools.env"
    assert expected in sync_sites.sync_sites(tmp_path, check=True)
    assert not expected.exists()


def test_sync_only_manages_actions_and_qinglong(tmp_path):
    workflow = tmp_path / ".github" / "workflows" / "checkin.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        (sync_sites.REPO_ROOT / ".github" / "workflows" / "checkin.yml").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    readme = tmp_path / "README.md"
    guide = tmp_path / "docs" / "qinglong.md"
    guide.parent.mkdir(parents=True)
    readme.write_text("manual README", encoding="utf-8")
    guide.write_text("manual guide", encoding="utf-8")

    sync_sites.sync_sites(tmp_path)

    assert readme.read_text(encoding="utf-8") == "manual README"
    assert guide.read_text(encoding="utf-8") == "manual guide"
    assert not (tmp_path / ".env.example").exists()


def test_ci_workflow_does_not_reference_checkin_secrets():
    ci = (sync_sites.REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    for definition in sync_sites.SITE_DEFINITIONS:
        assert all(env_key not in ci for env_key in definition.credentials.values())
