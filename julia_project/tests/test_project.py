from julia_project import JuliaProject
import os
from unittest import mock
import logging
import pytest


@pytest.fixture
@mock.patch.dict(os.environ, {"MY_MOD_COMPILE": "n", "MY_MOD_INSTALL_JULIA": "n"})
def run_proj():
    jp = JuliaProject(name="mymod", package_path="./julia_project/tests/project", env_prefix='MY_MOD_', logging_level=logging.INFO)
    jp.run()
    return jp


@pytest.mark.julia
def test_full_sys_path(run_proj):
    assert run_proj.full_sys_image_dir_path == './julia_project/tests/project/sys_image'


@pytest.mark.julia
def test_manifest_toml(run_proj):
    assert run_proj.manifest_toml == './julia_project/tests/project/Manifest.toml'

# @pytest.mark.julia
# @mock.patch.dict(os.environ, {"MY_MOD_COMPILE": "n", "MY_MOD_INSTALL_JULIA": "n"})
# def test_run_julia():
#     jp = JuliaProject(name="mymod", package_path="./julia_project/tests/project", env_prefix='MY_MOD_', logging_level=logging.INFO)
#     jp.run()
#     assert jp.full_sys_image_dir_path == './julia_project/tests/project/sys_image'


#
