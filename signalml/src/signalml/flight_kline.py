"""
从仓库根目录加载 `flight_kline_client.py`，与 data.py 共用同一份 Flight 实现。

signalml 作为子包安装时，通过路径定位到 checkout 根目录下的单文件模块。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CLIENT_PATH = Path(__file__).resolve().parents[3] / "flight_kline_client.py"
_MOD_NAME = "flight_kline_client._runtime_signalml"


def _load_client():
    if not _CLIENT_PATH.is_file():
        raise ImportError(
            f"未找到 {_CLIENT_PATH}。请在 signalview 仓库根目录使用 signalml，"
            "或把 flight_kline_client.py 置于 signalml 包上三级目录（仓库根）。"
        )
    if _MOD_NAME in sys.modules:
        return sys.modules[_MOD_NAME]
    spec = importlib.util.spec_from_file_location(_MOD_NAME, _CLIENT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {_CLIENT_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MOD_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


def __getattr__(name: str):
    if name.startswith("_"):
        raise AttributeError(name)
    return getattr(_load_client(), name)


def __dir__():
    return dir(_load_client())
