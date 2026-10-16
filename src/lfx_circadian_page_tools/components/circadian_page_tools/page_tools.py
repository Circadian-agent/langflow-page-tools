"""One explicit action and output per paid Page Tools request."""

from typing import ClassVar

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from lfx_circadian_page_tools.client import fetch_page


class CircadianPageTools(Component):
    display_name = "Circadian Page Tools"
    description = (
        "Extract Markdown or HTML metadata from an authorized public URL. External API charges apply."
    )
    name = "CircadianPageTools"
    icon = "FileText"
    documentation = "https://api.market/store/circadian/page-tools"

    inputs: ClassVar[list] = [
        SecretStrInput(
            name="api_key",
            display_name="API.market API Key",
            required=True,
            password=True,
            info="Enable Page Tools on API.market. Store the key as a secret global variable before exporting flows.",
        ),
        DropdownInput(
            name="action",
            display_name="Action",
            options=["Extract Markdown", "Page Metadata"],
            value="Extract Markdown",
            info="One request per execution. USD0.005/call on the public plan; check current marketplace pricing.",
        ),
        MessageTextInput(
            name="url",
            display_name="Page URL",
            required=True,
            tool_mode=True,
            info="Authorized public HTTP(S) page. No JavaScript rendering, authenticated pages or browser session.",
        ),
    ]
    outputs: ClassVar[list] = [Output(name="result", display_name="Page Data", method="fetch")]

    async def fetch(self) -> Data:
        endpoints = {"Extract Markdown": "extract", "Page Metadata": "meta"}
        if self.action not in endpoints:
            raise ValueError("Select Extract Markdown or Page Metadata.")
        endpoint = endpoints[self.action]
        result = await fetch_page(endpoint, self.api_key, self.url)
        data = Data(data=result, text_key="markdown" if endpoint == "extract" else "description")
        self.status = data
        return data
