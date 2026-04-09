#!/usr/bin/env python3
"""Test script for architecture optimization modules."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_context_compact():
    """Test Context Compact module."""
    print("\n" + "=" * 50)
    print("Testing Context Compact Module")
    print("=" * 50)
    
    from horbot.agent.context_compact import (
        estimate_tokens,
        compress_to_summary,
        extract_tool_info,
        compact_context,
    )
    
    # Test 1: Token estimation
    test_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I am doing well, thank you!"},
    ]
    tokens = estimate_tokens(test_messages)
    print(f"Test 1 - Token estimation: {tokens} tokens")
    assert tokens > 0, "Token estimation should return positive value"
    print("Test 1 PASSED")
    
    # Test 2: Compact context
    large_messages = test_messages * 100
    input_tokens = estimate_tokens(large_messages)
    result = compact_context(large_messages, max_tokens=500, preserve_recent=5)
    output_tokens = estimate_tokens(result)
    reduction = (1 - output_tokens / input_tokens) * 100
    print(f"Test 2 - Compression: {input_tokens} -> {output_tokens} tokens ({reduction:.1f}% reduction)")
    assert output_tokens < input_tokens, "Should reduce token count"
    print("Test 2 PASSED")
    
    # Test 3: Tool info extraction
    messages_with_tools = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "name": "read_file", "input": {"path": "/test.py"}},
            {"type": "tool_use", "name": "write_file", "input": {"path": "/output.txt"}},
        ]}
    ]
    tools = extract_tool_info(messages_with_tools)
    print(f"Test 3 - Tool extraction: {len(tools)} tools")
    assert len(tools) == 2, "Should extract 2 tools"
    print("Test 3 PASSED")
    
    print("Context Compact: ALL TESTS PASSED")
    return True


def test_worktree():
    """Test Worktree Isolation module."""
    print("\n" + "=" * 50)
    print("Testing Worktree Isolation Module")
    print("=" * 50)
    
    import tempfile
    import shutil
    from pathlib import Path
    
    from horbot.agent.worktree import WorktreeManager
    
    # Create temp directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "source"
        source_dir.mkdir()
        
        # Create test files
        (source_dir / "test.py").write_text("print('hello')")
        (source_dir / "README.md").write_text("# Test Project")
        
        # Create worktree manager
        worktrees_dir = Path(tmpdir) / "worktrees"
        manager = WorktreeManager(
            base_dir=worktrees_dir,
            source_dir=source_dir,
            auto_cleanup=False,
        )
        
        # Test 1: Create worktree
        worktree_path = manager.create_worktree("test_task_123", copy_source=True)
        print(f"Test 1 - Create worktree: {worktree_path}")
        assert Path(worktree_path).exists(), "Worktree should exist"
        assert (Path(worktree_path) / "test.py").exists(), "test.py should be copied"
        print("Test 1 PASSED")
        
        # Test 2: List worktrees
        worktrees = manager.list_worktrees()
        print(f"Test 2 - List worktrees: {len(worktrees)} found")
        assert "test_task_123" in worktrees, "Should find created worktree"
        print("Test 2 PASSED")
        
        # Test 3: Cleanup worktree
        success = manager.cleanup_worktree("test_task_123")
        print(f"Test 3 - Cleanup worktree: {success}")
        assert success, "Cleanup should succeed"
        assert not Path(worktree_path).exists(), "Worktree should be removed"
        print("Test 3 PASSED")
    
    print("Worktree Isolation: ALL TESTS PASSED")
    return True


def test_team_protocols():
    """Test Team Protocols module."""
    print("\n" + "=" * 50)
    print("Testing Team Protocols Module")
    print("=" * 50)
    
    import asyncio
    from datetime import datetime
    
    from horbot.agent.team_protocols import (
        AgentMessage,
        AgentMailbox,
        ActionType,
        MessagePriority,
        TeamCoordinator,
        TaskBoard,
    )
    
    # Test 1: Message serialization
    msg = AgentMessage(
        sender="agent_a",
        receiver="agent_b",
        action=ActionType.TASK_ASSIGN,
        payload={"task": "test"},
        timestamp=datetime.now(),
    )
    json_data = msg.to_json()
    restored = AgentMessage.from_json(json_data)
    print(f"Test 1 - Message serialization: {restored.action.value}")
    assert restored.sender == "agent_a", "Sender should match"
    assert restored.action == ActionType.TASK_ASSIGN, "Action should match"
    print("Test 1 PASSED")
    
    # Test 2: Team coordinator
    coordinator = TeamCoordinator("test_coordinator")
    mailbox = coordinator.register_agent("worker_1", {"file_ops", "shell"})
    print(f"Test 2 - Register agent: worker_1")
    assert "worker_1" in coordinator._mailboxes, "Agent should be registered"
    print("Test 2 PASSED")
    
    # Test 3: Task board
    async def test_task_board():
        board = TaskBoard()
        await board.add_task(
            task_id="task_001",
            title="Test Task",
            description="A test task",
            required_capabilities={"file_ops"},
        )
        tasks = await board.list_tasks(status="pending")
        print(f"Test 3 - Task board: {len(tasks)} tasks")
        assert len(tasks) == 1, "Should have 1 task"
        
        # Test claim
        claimed = await board.claim_task("task_001", "worker_1")
        assert claimed, "Claim should succeed"
        print("Test 3 PASSED")
    
    asyncio.run(test_task_board())
    
    print("Team Protocols: ALL TESTS PASSED")
    return True


def test_autonomous():
    """Test Autonomous Agents module."""
    print("\n" + "=" * 50)
    print("Testing Autonomous Agents Module")
    print("=" * 50)
    
    import asyncio
    from horbot.agent.autonomous import (
        AutonomousAgent,
        AutonomousAgentConfig,
        AutonomousAgentManager,
        AgentState,
    )
    from horbot.agent.team_protocols import TaskBoard
    
    async def test_autonomous_agent():
        # Test 1: Create agent
        executed_tasks = []
        
        async def mock_executor(task):
            executed_tasks.append(task)
            return {"status": "completed", "result": "test result"}
        
        agent = AutonomousAgent(
            agent_id="test_worker",
            capabilities={"file_ops", "shell"},
            task_executor=mock_executor,
            config=AutonomousAgentConfig(
                enabled=True,
                idle_interval=0.1,
                task_timeout=5.0,
            ),
        )
        
        print(f"Test 1 - Create agent: {agent.agent_id}")
        assert agent.state == AgentState.IDLE, "Agent should be idle"
        print("Test 1 PASSED")
        
        # Test 2: Start and stop
        await agent.start()
        print(f"Test 2 - Start agent: running={agent._running}")
        assert agent._running, "Agent should be running"
        
        await agent.stop()
        print(f"Test 2 - Stop agent: running={agent._running}")
        assert not agent._running, "Agent should be stopped"
        print("Test 2 PASSED")
        
        # Test 3: Task claiming
        board = TaskBoard()
        agent.task_board = board
        
        await board.add_task(
            task_id="test_task_001",
            title="Test Task",
            description="A test task for autonomous agent",
            required_capabilities={"file_ops"},
        )
        
        can_handle = agent._can_handle({"required_capabilities": ["file_ops"]})
        print(f"Test 3 - Can handle task: {can_handle}")
        assert can_handle, "Agent should be able to handle task"
        print("Test 3 PASSED")
        
        # Test 4: Manager
        manager = AutonomousAgentManager()
        agent2 = manager.create_agent(
            agent_id="worker_2",
            capabilities={"file_ops"},
            task_executor=mock_executor,
        )
        print(f"Test 4 - Manager create agent: {agent2.agent_id}")
        assert len(manager.list_agents()) == 1, "Should have 1 agent"
        print("Test 4 PASSED")
    
    asyncio.run(test_autonomous_agent())
    
    print("Autonomous Agents: ALL TESTS PASSED")
    return True


def main():
    """Run all tests."""
    print("=" * 50)
    print("Architecture Optimization Module Tests")
    print("=" * 50)
    
    results = {}
    
    try:
        results["context_compact"] = test_context_compact()
    except Exception as e:
        print(f"Context Compact FAILED: {e}")
        results["context_compact"] = False
    
    try:
        results["worktree"] = test_worktree()
    except Exception as e:
        print(f"Worktree FAILED: {e}")
        results["worktree"] = False
    
    try:
        results["team_protocols"] = test_team_protocols()
    except Exception as e:
        print(f"Team Protocols FAILED: {e}")
        results["team_protocols"] = False
    
    try:
        results["autonomous"] = test_autonomous()
    except Exception as e:
        print(f"Autonomous FAILED: {e}")
        results["autonomous"] = False
    
    print("\n" + "=" * 50)
    print("Test Results Summary")
    print("=" * 50)
    for module, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  {module}: {status}")
    
    all_passed = all(results.values())
    print("\n" + ("ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED"))
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
