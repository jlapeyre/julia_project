from julia_project import JuliaProject

import os
import unittest
from unittest import mock
import logging
import pytest

def test_emtpy_init():
    with pytest.raises(TypeError):
        JuliaProject()


def test_one_arg_init():
    with pytest.raises(TypeError):
        JuliaProject(name="mymod")


def test_min_init():
    jp = JuliaProject(name="mymod", package_path=".")
    assert jp.name == "mymod"
    assert jp.package_path ==  "."
    assert jp.env_prefix == "JULIA_PROJECT_"
    assert jp.registry_url is None
    assert jp.sys_image_file_base == 'sys_mymod'
    assert jp.sys_image_dir == 'sys_image'
    assert jp._console_logging == False
    assert jp._logging_level == None
    assert jp._SETUP == False
    assert jp._question_results == {'install': None, 'compile': None}


@pytest.fixture
def gen_jp():
    jp = JuliaProject(name="mymod", package_path=".", env_prefix='MY_MOD_')
    return jp


def test_simple_methods(gen_jp):
    assert gen_jp._envname('COMPILE') == 'MY_MOD_COMPILE'


def test_no_log_handler(gen_jp):
    gen_jp.setup()
    assert len(gen_jp.logger.handlers) == 0


@mock.patch.dict(os.environ, {"MY_MOD_COMPILE": "y", "MY_MOD_INSTALL_JULIA": "n"})
def test_env_var_1(gen_jp):
    gen_jp.setup()
    assert gen_jp._question_results['compile'] == True
    assert gen_jp._question_results['install'] == False


@mock.patch.dict(os.environ, {"MY_MOD_COMPILE": "n", "MY_MOD_INSTALL_JULIA": "y"})
def test_env_var_2(gen_jp):
    gen_jp.setup()
    assert gen_jp._question_results['compile'] == False
    assert gen_jp._question_results['install'] == True


@mock.patch.dict(os.environ, {"MY_MOD_JULIA_PATH": "/a/julia/path"})
def test_env_var_3(gen_jp):
    gen_jp.setup()
    gen_jp.find_julia()
    assert gen_jp.julia_path == "/a/julia/path"
    assert gen_jp._question_results['install'] == False
