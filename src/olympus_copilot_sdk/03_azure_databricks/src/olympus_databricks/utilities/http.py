from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, cast
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from olympus_databricks.api_ingestion import ApiPage, TransientApiError


class HttpJsonTransport:
    def __init__(
        self,
        base_url: str,
        token: str,
        records_field: str,
        cursor_field: str,
    ) -> None:
        if urlsplit(base_url).scheme != "https":
            raise ValueError("API base_url must use HTTPS")
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._records_field = records_field
        self._cursor_field = cursor_field

    def fetch(self, path: str, cursor: str | None) -> ApiPage:
        query = urlencode({"cursor": cursor}) if cursor else ""
        url = f"{self._base_url}{path}{'?' + query if query else ''}"
        request = Request(  # noqa: S310
            url,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        try:
            with urlopen(request, timeout=60) as response:  # noqa: S310  # nosec B310
                payload: object = json.loads(response.read())
        except HTTPError as error:
            if error.code == 429 or error.code >= 500:
                raise TransientApiError(f"API returned HTTP {error.code}") from error
            raise
        if not isinstance(payload, dict):
            raise ValueError("API response must be an object")
        body = cast(dict[str, object], payload)
        records_value = body.get(self._records_field, [])
        if not isinstance(records_value, list):
            raise ValueError(f"API field {self._records_field!r} must be a list of objects")
        records = cast(list[object], records_value)
        if not all(isinstance(record, Mapping) for record in records):
            raise ValueError(f"API field {self._records_field!r} must be a list of objects")
        cursor_value = body.get(self._cursor_field)
        if cursor_value is not None and not isinstance(cursor_value, str):
            raise ValueError(f"API field {self._cursor_field!r} must be a string or null")
        return ApiPage(cast(list[Mapping[str, Any]], records), cursor_value)
