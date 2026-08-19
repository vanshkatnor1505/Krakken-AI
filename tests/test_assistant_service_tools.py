from collections.abc import Iterator, Sequence

from core.ai.models import AIChunk, AIResponse, ChatMessage
from core.ai.provider import AIProvider
from core.events.event_bus import EventBus
from core.services.assistant_service import AssistantService
from core.tools.models import ToolDefinition


class FakeProvider(AIProvider):
    def chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition] | None = None,
    ) -> AIResponse:
        return AIResponse(content="ok", model="fake")

    def stream(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolDefinition] | None = None,
    ) -> Iterator[AIChunk]:
        yield AIChunk(content="ok")
        yield AIChunk(finished=True, finish_reason="stop")


class FakeToolManager:
    count = 1

    def get_tool_names(self) -> list[str]:
        return ["fake_tool"]

    def get_tool_definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="fake_tool",
                description="A fake tool used by tests.",
                parameters={"type": "object", "properties": {}},
            )
        ]


def test_assistant_service_returns_registered_tool_definitions():
    service = AssistantService(
        event_bus=EventBus(),
        provider=FakeProvider(),
        tool_manager=FakeToolManager(),
    )

    definitions = service._get_tool_definitions()

    assert [definition.name for definition in definitions] == ["fake_tool"]
