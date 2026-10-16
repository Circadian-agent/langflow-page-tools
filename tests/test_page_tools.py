import json
from pathlib import Path

import httpx
import pytest
from lfx.extension.loader import load_extension
from lfx.graph import Graph

from lfx_circadian_page_tools import CircadianPageTools
from lfx_circadian_page_tools import client as api

KEY = "fixture-only-key"
URL = "https://example.com/?a=one&b=two%20words"
EXTRACT = {
    "ok": True,
    "httpStatus": 200,
    "truncated": False,
    "url": URL,
    "finalUrl": URL,
    "title": "Fixture",
    "description": None,
    "markdown": "# Fixture\n\nA paragraph.",
    "wordCount": 3,
    "links": [],
}
META = {
    "ok": True,
    "httpStatus": 200,
    "truncated": True,
    "url": URL,
    "title": "Fixture",
    "description": None,
    "openGraph": {"og:title": "Fixture"},
    "twitter": {},
    "jsonLd": [{"@type": "Article"}],
}


@pytest.fixture
def gateway(monkeypatch):
    real_client = httpx.AsyncClient
    calls = []

    def install(handler):
        def record(request):
            calls.append(request)
            return handler(request)

        def factory(**kwargs):
            assert kwargs["follow_redirects"] is False
            assert kwargs["timeout"].connect == 5.0
            assert kwargs["timeout"].read == 25.0
            return real_client(transport=httpx.MockTransport(record), **kwargs)

        monkeypatch.setattr(api.httpx, "AsyncClient", factory)
        return calls

    return install


def component(action="Extract Markdown", url=URL, key=KEY):
    result = CircadianPageTools()
    result.set(action=action, url=url, api_key=key)
    return result


class TestCircadianPageTools:
    @pytest.mark.parametrize(
        "action,endpoint,payload",
        [
            ("Extract Markdown", "extract", EXTRACT),
            ("Page Metadata", "meta", META),
        ],
    )
    async def test_real_component_preserves_data_and_sends_one_request(
        self, gateway, action, endpoint, payload
    ):
        calls = gateway(lambda request: httpx.Response(200, json=payload))
        instance = component(action)
        result = await instance.fetch()
        assert result.data == payload
        assert instance.status == result
        assert len(calls) == 1
        request = calls[0]
        assert request.method == "GET"
        assert str(request.url).split("?")[0] == api.BASE_URL + endpoint
        assert request.url.params["url"] == URL
        assert request.headers["x-api-market-key"] == KEY
        assert KEY not in str(request.url)
        assert KEY not in json.dumps(result.data)
        if endpoint == "extract":
            assert result.get_text() == payload["markdown"]

    @pytest.mark.parametrize("status", [301, 302, 400, 401, 402, 403, 404, 429, 500, 503])
    async def test_gateway_failure_never_follows_or_retries_or_echoes_body(self, gateway, status):
        calls = gateway(
            lambda request: httpx.Response(
                status,
                text=f"private {KEY}",
                headers={"Location": "https://unrelated.example/"},
            )
        )
        with pytest.raises(ValueError, match=f"HTTP {status}") as error:
            await component().fetch()
        assert KEY not in str(error.value)
        assert "No automatic retry" in str(error.value)
        assert len(calls) == 1

    async def test_timeout_is_ambiguous_and_not_retried(self, gateway):
        def timeout(request):
            raise httpx.ReadTimeout(f"private {KEY}", request=request)

        calls = gateway(timeout)
        with pytest.raises(ValueError, match="may already have been charged") as error:
            await component().fetch()
        assert KEY not in str(error.value)
        assert error.value.__suppress_context__ is True
        assert len(calls) == 1

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost/",
            "http://127.0.0.1/",
            "http://[::1]/",
            "http://10.0.0.1/",
            "http://169.254.169.254/",
            "https://intranet/",
            "https://test.local/",
            "https://user:pass@example.com/",
            "file:///etc/passwd",
            "https://example.com:8443/",
            "https://example.com/#token",
            "https://example.com\\@localhost/",
            "https://example.com/\n",
        ],
    )
    async def test_bad_url_never_contacts_gateway(self, gateway, url):
        calls = gateway(lambda request: pytest.fail("Invalid URL caused a request"))
        with pytest.raises(ValueError, match="public HTTP"):
            await component(url=url).fetch()
        assert not calls

    @pytest.mark.parametrize("key", ["", "key\nvalue", "key value", "é", "a" * 513])
    async def test_bad_key_never_contacts_gateway(self, gateway, key):
        calls = gateway(lambda request: pytest.fail("Invalid key caused a request"))
        with pytest.raises(ValueError):
            await component(key=key).fetch()
        assert not calls

    @pytest.mark.parametrize(
        "payload",
        [
            [],
            {"ok": False},
            {**EXTRACT, "httpStatus": True},
            {**EXTRACT, "truncated": "false"},
            {**EXTRACT, "markdown": None},
        ],
    )
    async def test_malformed_success_rejected(self, gateway, payload):
        calls = gateway(lambda request: httpx.Response(200, json=payload))
        with pytest.raises(ValueError):
            await component().fetch()
        assert len(calls) == 1

    async def test_metadata_schema_rejected(self, gateway):
        gateway(lambda request: httpx.Response(200, json={**META, "jsonLd": {}}))
        with pytest.raises(ValueError, match="incomplete metadata"):
            await component("Page Metadata").fetch()

    async def test_target_http_error_is_not_a_success(self, gateway):
        gateway(lambda request: httpx.Response(200, json={**EXTRACT, "httpStatus": 404}))
        with pytest.raises(ValueError, match="target page returned HTTP 404"):
            await component().fetch()

    @pytest.mark.parametrize("body,content_type", [(b"not json", "application/json"), (b"{}", "text/html")])
    async def test_non_json_rejected(self, gateway, body, content_type):
        gateway(lambda request: httpx.Response(200, content=body, headers={"content-type": content_type}))
        with pytest.raises(ValueError):
            await component().fetch()

    async def test_response_size_is_bounded(self, gateway):
        gateway(
            lambda request: httpx.Response(
                200,
                content=b" " * (api.MAX_RESPONSE_BYTES + 1),
                headers={"content-type": "application/json"},
            )
        )
        with pytest.raises(ValueError, match="size limit"):
            await component().fetch()

    async def test_invalid_action_cannot_change_gateway(self, gateway):
        calls = gateway(lambda request: pytest.fail("Invalid action caused a request"))
        with pytest.raises(ValueError, match="Select"):
            await component("https://other.example/").fetch()
        assert not calls

    async def test_agent_tool_hides_key_and_executes_selected_action(self, gateway):
        calls = gateway(lambda request: httpx.Response(200, json=EXTRACT))
        instance = component()
        tools = await instance.to_toolkit()
        assert len(tools) == 1
        assert set(tools[0].args) == {"url"}
        assert KEY not in json.dumps(tools[0].args)
        assert not calls  # Building the tool must not probe the paid API.
        result = await tools[0].ainvoke({"url": URL})
        assert len(calls) == 1
        assert calls[0].url.path.endswith("/extract")
        assert "Fixture" in str(result)

    async def test_graph_execution_preserves_output_with_one_gateway_request(self, gateway):
        calls = gateway(lambda request: httpx.Response(200, json=EXTRACT))
        instance = component()
        graph = Graph(instance, instance)
        results = [step async for step in graph.async_start()]
        built = [step for step in results if hasattr(step, "result_dict")]
        assert len(built) == 1
        assert built[0].valid
        assert built[0].result_dict.outputs["result"]["message"] == EXTRACT
        assert len(calls) == 1

    def test_real_extension_loader_and_editor_schema(self):
        root = Path(api.__file__).parent
        loaded = load_extension(root)
        assert not loaded.errors
        assert not loaded.warnings
        assert len(loaded.components) == 1
        assert loaded.components[0].class_name == "CircadianPageTools"
        instance = loaded.components[0].klass()
        node = instance.to_frontend_node()["data"]["node"]
        assert node["template"]["api_key"]["password"] is True
        assert not node["template"]["api_key"].get("tool_mode", False)
        assert node["template"]["url"]["tool_mode"] is True
        assert len(node["outputs"]) == 1
