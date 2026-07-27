#!/usr/bin/python3.11

import io
from typing import Any

from fdk import response

from modules.app import run_update


def handler(ctx: Any, data: io.BytesIO | None = None) -> Any:
    status_code, response_data = run_update()

    return response.Response(ctx,
                             status_code=status_code,
                             response_data=response_data,
                             headers={'Content-Type': 'text/plain'})
