"""Temporarily prevent Windows sleep while a target process is alive."""

from __future__ import annotations

import argparse
import ctypes


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    args = parser.parse_args()

    kernel32 = ctypes.windll.kernel32
    process_handle = kernel32.OpenProcess(SYNCHRONIZE, False, args.pid)
    if not process_handle:
        return 2
    try:
        previous = kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
        if not previous:
            return 3
        kernel32.WaitForSingleObject(process_handle, INFINITE)
    finally:
        kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        kernel32.CloseHandle(process_handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
