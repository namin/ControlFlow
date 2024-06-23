import random
from typing import Annotated

import pytest
from controlflow.agents.agent import Agent
from controlflow.llm.messages import ToolMessage
from controlflow.llm.tools import (
    Tool,
    handle_invalid_tool_call,
    handle_tool_call,
    handle_tool_call_async,
    tool,
)
from pydantic import Field


@pytest.mark.parametrize("style", ["decorator", "class"])
class TestToolFunctions:
    def test_decorator(self, style):
        def roll_die():
            return 2

        if style == "class":
            roll_die_tool = Tool.from_function(roll_die)
        elif style == "decorator":
            roll_die_tool = tool(roll_die)

        assert roll_die_tool.invoke({}) == 2

    async def test_decorator_async(self, style):
        async def roll_die():
            return 2

        if style == "class":
            roll_die_tool = Tool.from_function(roll_die)
        elif style == "decorator":
            roll_die_tool = tool(roll_die)

        assert roll_die_tool.invoke({}) == 2
        assert await roll_die_tool.ainvoke({}) == 2

    def test_tool_does_not_require_docstring(self, style):
        def roll_die():
            return random.randint(1, 6)

        if style == "class":
            roll_die_tool = Tool.from_function(roll_die)
        elif style == "decorator":
            roll_die_tool = tool(roll_die)

        assert roll_die_tool.description == "roll_die"

    def test_tool_gets_docstring_from_description(self, style):
        def roll_die():
            """Roll a die."""
            return random.randint(1, 6)

        if style == "class":
            roll_die_tool = Tool.from_function(roll_die)
        elif style == "decorator":
            roll_die_tool = tool(roll_die)

        assert roll_die_tool.description == "Roll a die."

    def test_tool_gets_name_from_function_name(self, style):
        def roll_die():
            """Roll a die."""
            return random.randint(1, 6)

        if style == "class":
            roll_die_tool = Tool.from_function(roll_die)
        elif style == "decorator":
            roll_die_tool = tool(roll_die)

        assert roll_die_tool.name == "roll_die"

    def test_args_schema_types(self, style):
        def add(a: int, b: float, c):
            return a + b

        if style == "class":
            add_tool = Tool.from_function(add)
        elif style == "decorator":
            add_tool = tool(add)

        schema = add_tool.args_schema.schema()
        assert schema["properties"]["a"]["type"] == "integer"
        assert schema["properties"]["b"]["type"] == "number"
        assert "type" not in schema["properties"]["c"]

    def test_load_arg_description_from_annotated(self, style):
        def add(a: Annotated[int, "the first number"], b: float):
            return a + b

        if style == "class":
            add_tool = Tool.from_function(add)
        elif style == "decorator":
            add_tool = tool(add)

        schema = add_tool.args_schema.schema()
        assert schema["properties"]["a"]["description"] == "the first number"
        assert "description" not in schema["properties"]["b"]

    def test_laod_arg_description_from_field(self, style):
        def add(a: int = Field(description="The first number."), b: float = None):
            return a

        if style == "class":
            add_tool = Tool.from_function(add)
        elif style == "decorator":
            add_tool = tool(add)

        schema = add_tool.args_schema.schema()
        assert schema["properties"]["a"]["description"] == "The first number."
        assert "description" not in schema["properties"]["b"]


class TestToolDecorator:
    def test_provide_name(self):
        @tool(name="roll_die")
        def foo():
            return 2

        assert foo.name == "roll_die"

    def test_provide_description(self):
        @tool(description="Roll a die.")
        def foo():
            return 2

        assert foo.description == "Roll a die."


class TestRunTools:
    def invoke_tool(self):
        @tool
        def foo():
            return 2

        assert foo.invoke({}) == 2

    async def invoke_tool_async(self):
        @tool
        async def foo():
            return 2

        assert foo.invoke({}) == 2
        assert await foo.ainvoke({}) == 2

    def invoke_with_args(self):
        @tool
        def add(a: int, b: int):
            return a + b

        assert add.invoke({"a": 2, "b": 3}) == 5

    def invocation_error(self):
        @tool
        def foo():
            raise ValueError("This is an error.")

        with pytest.raises(ValueError):
            foo.invoke({})


class TestHandleTools:
    def handle_tool_call(self):
        @tool
        def foo():
            return 2

        tool_call = {"name": "foo", "args": {}}
        message = handle_tool_call(tool_call, tools=[foo])
        assert isinstance(message, ToolMessage)
        assert message.content == "2"
        assert message.tool_call_id == tool_call["id"]
        assert message.tool_call == tool_call
        assert message.tool_result == 2
        assert message.tool_metadata == {}

    def handle_tool_call_with_args(self):
        @tool
        def add(a: int, b: int):
            return a + b

        tool_call = {"name": "add", "args": {"a": 2, "b": 3}}
        message = handle_tool_call(tool_call, tools=[add])
        assert message.content == "5"

    async def handle_async_tool_call(self):
        @tool
        async def foo():
            return 2

        tool_call = {"name": "foo", "args": {}}
        message = await handle_tool_call_async(tool_call, tools=[foo])  # noqa: F821
        assert message.content == "2"

    async def handle_async_tool_call_with_sync_tool(self):
        @tool
        def foo():
            return 2

        tool_call = {"name": "foo", "args": {}}
        message = await handle_tool_call_async(tool_call, tools=[foo])
        assert message.content == "2"

    def handle_tool_call_with_async_tool(self):
        @tool
        async def foo():
            return 2

        tool_call = {"name": "foo", "args": {}}
        message = handle_tool_call(tool_call, tools=[foo])
        assert message.content == "2"

    def handle_error(self):
        @tool
        def foo():
            raise ValueError("This is an error.")

        tool_call = {"name": "foo", "args": {}}
        message = handle_tool_call(tool_call, tools=[foo])
        assert message.content == 'Error calling function "foo": This is an error.'
        assert message.tool_metadata["is_failed"]

    def handle_invalid_tool_call(self):
        tool_call = {"name": "foo", "args": {}}
        message = handle_invalid_tool_call(tool_call, tools=[])
        assert message.content == 'Function "foo" not found.'
        assert message.tool_metadata["is_failed"]

    def handle_tool_call_with_agent_id(self):
        @tool
        def foo():
            return 2

        agent = Agent(name="test-agent")

        tool_call = {"name": "foo", "args": {}}
        message = handle_tool_call(tool_call, tools=[foo], agent=agent)
        assert message.agent.name == "test-agent"
        assert message.agent.id == agent.id

    async def handle_async_tool_call_with_agent_id(self):
        @tool
        async def foo():
            return 2

        agent = Agent(name="test-agent")

        tool_call = {"name": "foo", "args": {}}
        message = await handle_tool_call_async(tool_call, tools=[foo], agent=agent)
        assert message.agent.name == "test-agent"
        assert message.agent.id == agent.id

    def handle_invalid_tool_call_with_agent_id(self):
        agent = Agent(name="test-agent")
        tool_call = {"name": "foo", "args": {}}
        message = handle_invalid_tool_call(tool_call, tools=[], agent=agent)
        assert message.agent.name == "test-agent"
        assert message.agent.id == agent.id
