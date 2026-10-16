from importlib.metadata import version

from wqf import __version__


def test_package_has_version() -> None:
    # Garante que pyproject.toml, uv.lock e src/wqf/__init__.py estejam em sincronia.
    assert __version__ == version("wolf-quant-fund")
