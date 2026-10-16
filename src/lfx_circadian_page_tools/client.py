"""Fixed-gateway client. Target URLs are data sent to the Page Tools service."""

import ipaddress
import json
from urllib.parse import urlsplit

import httpx

BASE_URL = "https://prod.api.market/api/v1/circadian/page-tools/api/"
MAX_RESPONSE_BYTES = 2_000_000


def validate_key(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 512:
        raise ValueError("Enter your API.market key in the private credential field.")
    if any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ValueError("The API.market key must not contain whitespace or non-ASCII characters.")
    return value


def validate_url(value: object) -> str:
    message = "Enter an authorized public HTTP(S) URL without credentials, fragments or a custom port."
    if not isinstance(value, str) or not value or len(value) > 8192:
        raise ValueError(message)
    if any(ord(c) <= 32 or ord(c) == 127 for c in value) or "\\" in value:
        raise ValueError(message)
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if (
            parsed.scheme not in ("http", "https")
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or parsed.port not in (None, 80 if parsed.scheme == "http" else 443)
        ):
            raise ValueError(message)
        # DNS resolution and redirect targets are checked by the backend. This
        # local check catches common mistakes without making another request.
        if "%" in host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError(message)
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host:
                raise ValueError(message) from None
        else:
            if not address.is_global:
                raise ValueError(message)
    except ValueError:
        raise ValueError(message) from None
    return value


async def fetch_page(endpoint: str, api_key: object, target: object) -> dict:
    if endpoint not in ("extract", "meta"):
        raise ValueError("Unsupported Page Tools action.")
    key = validate_key(api_key)
    url = validate_url(target)
    try:
        # One request, no redirects, no application-level retries. An uncertain
        # response may already have been charged by the external provider.
        async with (
            httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=5.0), follow_redirects=False) as client,
            client.stream(
                "GET",
                BASE_URL + endpoint,
                params={"url": url},
                headers={"x-api-market-key": key, "Accept": "application/json"},
            ) as response,
        ):
            status = response.status_code
            if status != 200:
                if status in (401, 403):
                    detail = "Check the API.market key and Page Tools access."
                elif status == 402:
                    detail = "Check the Page Tools plan and API.market wallet balance."
                elif status == 429:
                    detail = "The API limit was reached. Wait before trying again."
                else:
                    detail = "Check Page Tools access and the target URL."
                raise ValueError(
                    f"Page Tools gateway returned HTTP {status}. {detail} No automatic retry was made."
                )
            if "application/json" not in response.headers.get("content-type", "").lower():
                raise ValueError(
                    "Page Tools returned an unexpected response format. No automatic retry was made."
                )
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError(
                        "Page Tools response exceeded the size limit. No automatic retry was made."
                    )
        result = json.loads(body)
    except httpx.HTTPError:
        raise ValueError(
            "Page Tools request failed or timed out. It may already have been charged. Check usage before retrying."
        ) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Page Tools returned invalid JSON. No automatic retry was made.") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise ValueError("Page Tools did not return a successful result. No automatic retry was made.")
    status = result.get("httpStatus")
    if type(status) is not int or not 100 <= status <= 599 or type(result.get("truncated")) is not bool:
        raise ValueError("Page Tools returned an incomplete result. No automatic retry was made.")
    if status >= 400:
        raise ValueError(
            f"The target page returned HTTP {status}. This API call may be charged. No automatic retry was made."
        )
    if endpoint == "extract" and not isinstance(result.get("markdown"), str):
        raise ValueError("Page Tools returned no Markdown field.")
    if endpoint == "meta" and not all(
        isinstance(result.get(k), t) for k, t in (("openGraph", dict), ("twitter", dict), ("jsonLd", list))
    ):
        raise ValueError("Page Tools returned incomplete metadata.")
    return result
