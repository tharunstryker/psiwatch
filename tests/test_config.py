"""
test_config.py — TOML config loading and CLI arg merging.
"""

import os
import tempfile
import argparse
import pytest
from psiwatch.config import load_config, apply_config


@pytest.fixture
def cfg_path():
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False, mode="w") as f:
        f.write('[psiwatch]\npsi_threshold = 0.15\nfail_on_drift = true\ncolumns = ["age", "score"]\n')
        path = f.name
    yield path
    os.unlink(path)


def test_config_loads_values(cfg_path):
    cfg = load_config(explicit_path=cfg_path, silent=True)
    assert cfg.get("psi_threshold") == 0.15
    assert cfg.get("fail_on_drift") is True
    assert isinstance(cfg.get("columns"), list)


def test_apply_config_fills_unset_cli_args(cfg_path):
    cfg = load_config(explicit_path=cfg_path, silent=True)
    ns = argparse.Namespace(psi_threshold=None, fail_on_drift=False, columns=None,
                             ignore_columns=None, format=None, output=None,
                             silent=False, webhook=None)
    apply_config(ns, cfg)
    assert ns.psi_threshold == 0.15
    assert ns.fail_on_drift is True
    assert ns.columns is not None


def test_apply_config_cli_value_wins_over_config(cfg_path):
    cfg = load_config(explicit_path=cfg_path, silent=True)
    ns = argparse.Namespace(psi_threshold=0.30, fail_on_drift=False, columns=None,
                             ignore_columns=None, format=None, output=None,
                             silent=False, webhook=None)
    apply_config(ns, cfg)
    assert ns.psi_threshold == 0.30
