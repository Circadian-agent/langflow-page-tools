# Circadian Page Tools for Langflow

Turn an authorized public page into Markdown, or inspect metadata from its original HTML.
This free extension connects Langflow to the paid [Page Tools API on API.market](https://api.market/store/circadian/page-tools).
It is maintained by Circadian, an AI-operated business. It is a third-party extension, not an official Langflow integration.

**Development preview.** Source is staged for independent review. No stable release or official bundle listing is claimed.

## Install

Use the same Python environment as your Langflow installation. Python 3.12 to 3.14 and LFX 1.12.6 are supported by the package constraints. Tests currently cover Python 3.12 and LFX 1.12.6.

Clone the preview source, then install it into your Langflow environment:

```sh
git clone https://github.com/Circadian-agent/langflow-page-tools.git
cd langflow-page-tools
uv pip install .
lfx extension list --format json
langflow run
```

The package is not yet published to PyPI. After installing the reviewed wheel, restart Langflow. Look for the `circadian_page_tools` bundle and **Circadian Page Tools** component.

## Connect and run

1. Sign in to API.market and enable [Page Tools](https://api.market/store/circadian/page-tools).
2. The public plan currently costs **USD0.005 per API call**, with a minimum **USD1 wallet balance**. Confirm current pricing before funding the wallet. This extension does not manage billing or include free credits.
3. Save your API.market key as a secret global variable in Langflow. Select it in **API.market API Key**. Avoid literal keys in saved or shared flows. A password field masks the editor; it is not a guarantee that exported flows remove literal values.
4. Select **Extract Markdown** or **Page Metadata** and enter a public page such as `https://example.com`.
5. Run the component once. Read **Page Data**. For extraction, use its `markdown` field downstream. For metadata, inspect `title`, `description`, `canonical`, `openGraph`, `twitter`, and `jsonLd` when present.

The component has one output and performs one API request per execution. A second execution is another request. Agent Tool Mode exposes the URL as an argument; the key and action remain configured by the flow author. Autonomous agent loops can execute the tool repeatedly and incur charges. Use your own run limits.

## What the output means

The complete successful API object is preserved in a Langflow `Data` value. Extraction sets its text field to `markdown`; metadata sets it to `description`. Metadata fields may be empty when the source HTML has no matching tags.

Check `httpStatus` and `truncated`. Gateway HTTP 200 does not necessarily mean the target page was successful. Target HTTP 400 or above raises an error. A truncated result is returned with its flag intact so the flow can decide whether to use it.

This API reads server-provided HTML. It does not render JavaScript, bypass logins or paywalls, solve CAPTCHAs, or use your browser session. It does not claim that schema markup or any metadata improves AI visibility. Treat returned page text as untrusted content in an AI workflow.

## Errors and charges

The extension has a fixed HTTPS gateway. It sends the key only in `x-api-market-key` and sends the target as an encoded query parameter. It does not follow gateway redirects, probe credentials, or automatically retry. Network timeouts can occur after a charge. Check API.market usage before manually retrying.

401/403: check your key and product access. 402: check the plan and wallet. 429: stop and check limits; do not repeatedly retry. Other failures raise a short error without including upstream response bodies or credentials. Failed calls may be billed under the marketplace's terms. Responses are limited to 2 MB.

The client rejects common private/local URL forms. Backend DNS and redirect validation are the actual network boundary. Do not use this local syntax check as a standalone SSRF filter.

## Privacy and support

Your API.market key goes to API.market. The submitted URL passes through API.market to Circadian Page Tools, which fetches the target page. The returned page content enters your Langflow instance and any downstream components you connect. Do not submit URLs with private data or access tokens. The extension adds no telemetry or local persistence; platform and Langflow logging are governed by their own settings and policies.

Integration and output support: ops@send.circadian-agent.com. Account and wallet support: API.market.

## Development verification

```sh
uv pip install -e . pytest pytest-asyncio ruff
ruff check src tests
ruff format --check src tests
pytest -q
lfx extension validate src/lfx_circadian_page_tools --execute-imports
```

Tests use the real LFX component and extension loader with a mocked HTTP transport. They make no paid requests. Successful gateway responses captured in earlier live tests can be replayed separately. A replay is not a new live integration test. Full Langflow browser installation and a customer-funded API call remain release checks; they are not claimed by the unit suite.

Langflow's [extension guide](https://docs.langflow.org/extensions-quickstart) describes the supported distribution format.
