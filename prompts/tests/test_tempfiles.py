from tempfiles import TEMP_DIR, cleanup, new_temp_path


def test_new_temp_path_is_created_inside_temp_dir():
    path = new_temp_path(".wav")
    try:
        assert path.exists()
        assert TEMP_DIR.resolve() in path.resolve().parents
    finally:
        cleanup(path)


def test_cleanup_deletes_managed_temp_file():
    path = new_temp_path(".jpg")
    assert path.exists()

    cleanup(path)

    assert not path.exists()


def test_cleanup_does_not_touch_files_outside_temp_dir(tmp_path):
    outside_file = tmp_path / "keep_me.jpg"
    outside_file.write_bytes(b"data")

    cleanup(outside_file)

    assert outside_file.exists()


def test_cleanup_handles_none_gracefully():
    cleanup(None)  # should not raise
