import unittest

from horbot.agent.tools.base import Tool, ToolCategory, ToolMetadata
from horbot.agent.tools.registry import ToolRegistry


class DummyTool(Tool):
    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"dummy tool {self._name}"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self._name,
            description=self.description,
            category=ToolCategory.OTHER,
        )

    async def execute(self, **kwargs):
        return "ok"


class ToolRegistryTests(unittest.TestCase):
    def test_normalize_user_message_for_multimodal_content(self):
        content = [
            {"type": "text", "text": "请打开浏览器"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            {"type": "text", "text": "并查看页面标题"},
        ]

        normalized = ToolRegistry._normalize_user_message_for_matching(content)

        self.assertIn("请打开浏览器", normalized)
        self.assertIn("并查看页面标题", normalized)

    def test_get_definitions_smart_accepts_multimodal_content(self):
        registry = ToolRegistry()
        registry.register(DummyTool("message"))
        registry.register(DummyTool("browser"))
        registry.register(DummyTool("browser_click"))

        content = [
            {"type": "text", "text": "请打开浏览器并点击页面按钮"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
        ]

        definitions = registry.get_definitions_smart(content)
        names = {definition["function"]["name"] for definition in definitions}

        self.assertTrue(names)
        self.assertIn("browser", names)


if __name__ == "__main__":
    unittest.main()
