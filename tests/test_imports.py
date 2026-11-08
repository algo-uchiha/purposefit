import importlib
import pkgutil

import api

MODULES = sorted(m.name for m in pkgutil.walk_packages(api.__path__, "api."))


def test_found_every_module():
    expected = {"api.main", "api.cli", "api.pipeline.contracts", "api.pipeline.llm",
                "api.pipeline.redact.merge", "api.pipeline.generalise"}  # fmt: skip
    assert expected <= set(MODULES)
    assert len(MODULES) == 23


def test_every_module_imports():
    for name in MODULES:
        importlib.import_module(name)
