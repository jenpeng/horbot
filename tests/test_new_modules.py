#!/usr/bin/env python3
"""Test new modules: SkillLoader, TaskGraph, BackgroundNotifier"""

import asyncio
import sys


def test_skill_loader():
    """Test SkillLoader module."""
    print("\nTest 1: SkillLoader")
    from horbot.agent.skill_loader import SkillLoader
    loader = SkillLoader()
    stats = loader.get_cache_stats()
    print(f"  Cache stats: {stats}")
    print("  SkillLoader OK")
    return True


def test_task_graph():
    """Test TaskGraph module."""
    print("\nTest 2: TaskGraph")
    from horbot.agent.team_protocols import TaskGraph
    
    graph = TaskGraph()
    graph.add_task("t1")
    graph.add_task("t2", ["t1"])
    graph.add_task("t3", ["t1", "t2"])
    
    ready = graph.get_ready_tasks()
    assert ready == ["t1"], f"Expected [t1], got {ready}"
    print(f"  Initial ready: {ready}")
    
    graph.mark_completed("t1")
    ready = graph.get_ready_tasks()
    assert "t2" in ready, f"Expected t2 in ready, got {ready}"
    print(f"  After t1: {ready}")
    
    graph.mark_completed("t2")
    ready = graph.get_ready_tasks()
    assert "t3" in ready, f"Expected t3 in ready, got {ready}"
    print(f"  After t2: {ready}")
    
    order = graph.topological_sort()
    print(f"  Topological order: {order}")
    
    plan = graph.get_execution_plan()
    print(f"  Execution plan: {plan}")
    
    print("  TaskGraph OK")
    return True


async def test_background_notifier():
    """Test BackgroundNotifier module."""
    print("\nTest 3: BackgroundNotifier")
    from horbot.agent.background import BackgroundNotifier, TaskStatus
    
    notifier = BackgroundNotifier()
    
    async def sample_task():
        await asyncio.sleep(0.05)
        return "completed_result"
    
    task_id = await notifier.run_in_background("test_task", sample_task())
    print(f"  Started task: {task_id}")
    
    status = notifier.get_task_status(task_id)
    print(f"  Initial status: {status}")
    
    notification = await notifier.wait_for_notification(timeout=5)
    print(f"  Notification status: {notification.status.value}")
    assert notification.status == TaskStatus.COMPLETED
    
    task = notifier.get_task(task_id)
    print(f"  Result: {task.result}")
    assert task.result == "completed_result"
    
    summary = notifier.get_summary()
    print(f"  Summary: {summary}")
    
    print("  BackgroundNotifier OK")
    return True


def main():
    """Run all tests."""
    print("=" * 50)
    print("Testing New Modules")
    print("=" * 50)
    
    results = []
    
    try:
        results.append(("SkillLoader", test_skill_loader()))
    except Exception as e:
        print(f"  FAILED: {e}")
        results.append(("SkillLoader", False))
    
    try:
        results.append(("TaskGraph", test_task_graph()))
    except Exception as e:
        print(f"  FAILED: {e}")
        results.append(("TaskGraph", False))
    
    try:
        results.append(("BackgroundNotifier", asyncio.run(test_background_notifier())))
    except Exception as e:
        print(f"  FAILED: {e}")
        results.append(("BackgroundNotifier", False))
    
    print("\n" + "=" * 50)
    print("Test Results")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + ("ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED"))
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
