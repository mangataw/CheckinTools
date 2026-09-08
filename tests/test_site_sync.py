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
    expected = tmp_path / ".env.example"
    assert expected in sync_sites.sync_sites(tmp_path, check=True)
    assert not expected.exists()


def test_sync_repairs_managed_blocks(tmp_path):
    for relative in (
        ".github/workflows/checkin.yml",
        "README.md",
        "docs/qinglong.md",
    ):
        source = sync_sites.REPO_ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    workflow = tmp_path / ".github" / "workflows" / "checkin.yml"
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace("          - javbus", "          - drift"),
        encoding="utf-8",
    )

    assert workflow in sync_sites.sync_sites(tmp_path, check=True)
    sync_sites.sync_sites(tmp_path)
    assert sync_sites.sync_sites(tmp_path, check=True) == ()
