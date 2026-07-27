#!/usr/bin/python3.11

from modules.app import run_update


def main() -> int:
    status_code, response_data = run_update()
    print(response_data)
    return 0 if 200 <= status_code < 300 else 1


if __name__ == '__main__':
    raise SystemExit(main())
