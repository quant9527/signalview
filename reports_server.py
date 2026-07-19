"""本地报告文件 HTTP 服务。

为 backtest_reports 页面提供一个独立的只读 HTTP 服务，
用于在新窗口/标签页中打开 quant-lab/files 下的 HTML 报告。
服务绑定 127.0.0.1，仅本机可访问。
"""

import socket
import subprocess
import sys

QUANT_LAB_FILES = "/home/lei/repo/quant-lab/files"
REPORTS_SERVER_PORT = 8765

_reports_server_started = False


def start_reports_server() -> None:
    """启动独立子进程运行 http.server，提供 quant-lab/files 下的报告文件。"""
    global _reports_server_started
    if _reports_server_started:
        return

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        sock.connect(("127.0.0.1", REPORTS_SERVER_PORT))
        sock.close()
        _reports_server_started = True
        return
    except OSError:
        pass

    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "http.server",
            str(REPORTS_SERVER_PORT),
            "--bind",
            "127.0.0.1",
            "--directory",
            QUANT_LAB_FILES,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    _reports_server_started = True
