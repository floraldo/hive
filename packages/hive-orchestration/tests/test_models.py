"""
Tests for orchestration models.

Verifies that all models can be instantiated and have expected behavior.
"""
import pytest


@pytest.mark.core
def test_task_status_enum():
    """Test TaskStatus enum values."""
    from hive_orchestration.models import TaskStatus
    assert TaskStatus.QUEUED.value == 'queued'
    assert TaskStatus.COMPLETED.value == 'completed'
    assert TaskStatus.FAILED.value == 'failed'

@pytest.mark.core
def test_task_model_creation():
    """Test Task model can be created."""
    from hive_orchestration.models import Task, TaskStatus
    task = Task(title='Test Task', task_type='test', description='Test description', priority=5)
    assert task.title == 'Test Task'
    assert task.task_type == 'test'
    assert task.status == TaskStatus.QUEUED
    assert task.priority == 5
    assert task.id is not None
    assert task.created_at is not None

@pytest.mark.core
def test_task_lifecycle_methods():
    """Test Task lifecycle methods."""
    from hive_orchestration.models import Task, TaskStatus
    task = Task(title='Test', task_type='test')
    assert task.is_ready() is True
    assert task.is_terminal() is False
    task.assign_to_worker('worker-1')
    assert task.assigned_worker == 'worker-1'
    assert task.status == TaskStatus.ASSIGNED
    task.start_execution()
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.is_active() is True
    task.complete()
    assert task.status == TaskStatus.COMPLETED
    assert task.is_terminal() is True

@pytest.mark.core
def test_worker_model_creation():
    """Test Worker model can be created."""
    from hive_orchestration.models import Worker, WorkerStatus
    worker = Worker(role='executor', capabilities=['python', 'bash'])
    assert worker.role == 'executor'
    assert worker.status == WorkerStatus.ACTIVE
    assert 'python' in worker.capabilities
    assert worker.id is not None

@pytest.mark.core
def test_worker_capabilities():
    """Test Worker capability methods."""
    from hive_orchestration.models import Worker
    worker = Worker(role='executor', capabilities=['python', 'bash'])
    assert worker.has_capability('python') is True
    assert worker.has_capability('docker') is False
    assert worker.is_available() is True
    worker.assign_task('task-123')
    assert worker.current_task_id == 'task-123'
    assert worker.is_available() is False
    worker.complete_task()
    assert worker.current_task_id is None
    assert worker.is_available() is True

@pytest.mark.core
def test_run_model_creation():
    """Test Run model can be created."""
    from hive_orchestration.models import Run, RunStatus
    run = Run(task_id='task-123', worker_id='worker-456', run_number=1)
    assert run.task_id == 'task-123'
    assert run.worker_id == 'worker-456'
    assert run.run_number == 1
    assert run.status == RunStatus.PENDING

@pytest.mark.core
def test_run_lifecycle():
    """Test Run lifecycle methods."""
    from hive_orchestration.models import Run, RunStatus
    run = Run(task_id='task-1', worker_id='worker-1', run_number=1)
    run.start()
    assert run.status == RunStatus.RUNNING
    assert run.is_running() is True
    run.succeed({'result': 'success'})
    assert run.status == RunStatus.SUCCESS
    assert run.is_terminal() is True
    assert run.result_data == {'result': 'success'}
    assert run.duration is not None

@pytest.mark.core
def test_execution_plan_model():
    """Test ExecutionPlan model can be created."""
    from hive_orchestration.models import ExecutionPlan, PlanStatus
    plan = ExecutionPlan(title='Test Plan', total_subtasks=5)
    assert plan.title == 'Test Plan'
    assert plan.status == PlanStatus.PENDING
    assert plan.total_subtasks == 5
    assert plan.completed_subtasks == 0
    assert plan.get_progress_percentage() == 0.0

@pytest.mark.core
def test_execution_plan_progress():
    """Test ExecutionPlan progress tracking."""
    from hive_orchestration.models import ExecutionPlan
    plan = ExecutionPlan(title='Test', total_subtasks=10)
    plan.increment_completed()
    assert plan.completed_subtasks == 1
    assert plan.get_progress_percentage() == 10.0
    plan.increment_failed()
    assert plan.failed_subtasks == 1

@pytest.mark.core
def test_execution_plan_dependencies():
    """Test ExecutionPlan dependency management."""
    from hive_orchestration.models import ExecutionPlan
    plan = ExecutionPlan(title='Test')
    plan.add_dependency('task-2', 'task-1')
    plan.add_dependency('task-3', 'task-1')
    plan.add_dependency('task-3', 'task-2')
    assert plan.get_dependencies('task-2') == ['task-1']
    assert set(plan.get_dependencies('task-3')) == {'task-1', 'task-2'}

@pytest.mark.core
def test_subtask_model():
    """Test SubTask model."""
    from hive_orchestration.models import SubTask
    subtask = SubTask(id='subtask-1', title='Subtask', task_type='test', dependencies=['task-0'])
    assert subtask.id == 'subtask-1'
    assert subtask.has_dependencies() is True
