import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.policy_agent import PolicyAgent
from llm_common.agents import (
    AgenticExecutor,
    TaskPlanner,
    ToolContextManager,
    ToolRegistry,
    ToolSelector,
)


@pytest.fixture
def mock_llm_client():
    return MagicMock()


@pytest.fixture
def mock_tool_registry():
    registry = MagicMock(spec=ToolRegistry)
    registry.get_tools_schema.return_value = [
        {"name": f"tool_{i}"} for i in range(10)
    ]
    return registry


@pytest.fixture
def mock_context_manager():
    return MagicMock(spec=ToolContextManager)


@pytest.fixture
def mock_planner():
    planner = MagicMock(spec=TaskPlanner)
    planner.create_plan = AsyncMock(return_value=MagicMock(tasks=["task1"]))
    return planner


@pytest.fixture
def mock_selector():
    selector = MagicMock(spec=ToolSelector)
    mock_tools = [MagicMock(name=f"tool_{i}") for i in range(3)]
    selector.select_tools = AsyncMock(return_value=mock_tools)
    return selector


@pytest.fixture
def mock_executor():
    executor = MagicMock(spec=AgenticExecutor)
    executor.execute_plan = AsyncMock(return_value=[])
    return executor


@pytest.mark.asyncio
async def test_analyze_happy_path(
    mock_llm_client,
    mock_tool_registry,
    mock_context_manager,
    mock_planner,
    mock_selector,
    mock_executor,
):
    """Tests that selector, planner, and executor are called in order."""
    agent = PolicyAgent(
        llm_client=mock_llm_client,
        tool_registry=mock_tool_registry,
        context_manager=mock_context_manager,
        planner=mock_planner,
        selector=mock_selector,
        executor=mock_executor,
    )
    agent._synthesize_answer = AsyncMock(return_value="Final Answer")
    agent._load_context_blob = AsyncMock(return_value="context")

    await agent.analyze("test query")

    mock_selector.select_tools.assert_called_once()
    mock_planner.create_plan.assert_called_once()
    mock_executor.execute_plan.assert_called_once()


@pytest.mark.asyncio
async def test_planner_receives_selected_tools(
    mock_llm_client,
    mock_tool_registry,
    mock_context_manager,
    mock_planner,
    mock_selector,
    mock_executor,
):
    """Tests that the context passed to the planner contains the tools from the selector."""
    selected_tools = [MagicMock(name="SpecialTool1"), MagicMock(name="SpecialTool2")]
    mock_selector.select_tools = AsyncMock(return_value=selected_tools)

    agent = PolicyAgent(
        llm_client=mock_llm_client,
        tool_registry=mock_tool_registry,
        context_manager=mock_context_manager,
        planner=mock_planner,
        selector=mock_selector,
        executor=mock_executor,
    )
    agent._synthesize_answer = AsyncMock(return_value="Final Answer")
    agent._load_context_blob = AsyncMock(return_value="context")

    await agent.analyze("test query")

    args, kwargs = mock_planner.create_plan.call_args
    planner_context = kwargs.get("context", "")
    assert "SpecialTool1" in planner_context
    assert "SpecialTool2" in planner_context


@pytest.mark.asyncio
async def test_tool_selection_failure_is_handled(
    mock_llm_client,
    mock_tool_registry,
    mock_context_manager,
    mock_planner,
    mock_selector,
    mock_executor,
):
    """Tests that if the selector fails, the whole process fails gracefully."""
    mock_selector.select_tools.side_effect = Exception("Tool selection failed")

    agent = PolicyAgent(
        llm_client=mock_llm_client,
        tool_registry=mock_tool_registry,
        context_manager=mock_context_manager,
        planner=mock_planner,
        selector=mock_selector,
        executor=mock_executor,
    )

    result = await agent.analyze("test query")

    assert not result.success
    assert "Tool selection failed" in result.error
    mock_planner.create_plan.assert_not_called()
    mock_executor.execute_plan.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_stream_calls_selector(
    mock_llm_client,
    mock_tool_registry,
    mock_context_manager,
    mock_planner,
    mock_selector,
    mock_executor,
):
    """Tests that the streaming method also uses the tool selector."""

    agent = PolicyAgent(
        llm_client=mock_llm_client,
        tool_registry=mock_tool_registry,
        context_manager=mock_context_manager,
        planner=mock_planner,
        selector=mock_selector,
        executor=mock_executor,
    )

    async def mock_stream(*args, **kwargs):
        yield MagicMock()

    mock_executor.run_stream = mock_stream

    agent._synthesize_answer = AsyncMock(return_value="Final Answer")
    agent._load_context_blob = AsyncMock(return_value="context")

    events = []
    async for event in agent.analyze_stream("test query"):
        events.append(event)

    mock_selector.select_tools.assert_called_once()
    mock_planner.create_plan.assert_called_once()
