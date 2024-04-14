import os
import sys
import pytest
import logging
import shutil
from pathlib import Path
from io import StringIO
from migrate import MemoryStorageEngine, Migrator

logging.basicConfig(level=logging.DEBUG)


@pytest.fixture(params=['app_with_modules', 'basic_app', 'migrations_directory'])
def migration_setup(request):
    # Directly reference the path to the fixtures directory
    base_path = Path(__file__).resolve().parent / "fixtures" / request.param
    yield base_path


def test_memory_storage_engine(migration_setup, request):
    captured_output = StringIO()
    sys.stdout = captured_output

    directory_path = str(migration_setup)
    migrator = Migrator(directory=directory_path, storage_engine=MemoryStorageEngine('test_migrations'), dry_run=False)
    migrator.migrate()

    sys.stdout = sys.__stdout__

    if request.node.callspec.id == 'two_modules':
        assert "Hello, running up() from migration 20240410093757" in captured_output.getvalue()
        assert "Hello, running up() from migration 20240410093809" in captured_output.getvalue()
    elif request.node.callspec.id == 'basic_app' or request.node.callspec.id == 'single_dir':
        assert "Hello, running up() from migration 20240410094004" in captured_output.getvalue()
        assert "Hello, running up() from migration 20240410094006" in captured_output.getvalue()

