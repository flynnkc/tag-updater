#!/usr/bin/python3.11

import io
from typing import Any

from fdk.response import Response

from modules.app import run_update


def handler(ctx: Any, data: io.BytesIO | None = None) -> Response:
    status_code, response_data = run_update()

    return Response(ctx,
                    status_code=status_code,
                    response_data=response_data,
                    headers={'Content-Type': 'text/plain'})

def main() -> int:
    status_code, response_data = run_update()
    print(response_data)
    return 0 if 200 <= status_code < 300 else 1


if __name__ == '__main__':
    raise SystemExit(main())