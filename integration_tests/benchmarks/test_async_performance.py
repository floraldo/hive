"""
Performance benchmarks for async operations.
"""
import asyncio
import tempfile
from pathlib import Path

import aiofiles
import pytest


@pytest.mark.crust
class TestAsyncPerformance:
    """Benchmark tests for async operations."""

    @pytest.fixture
    def async_dataset(self):
        """Generate async test data."""
        return [{'id': i, 'data': f'async_data_{i}'} for i in range(1000)]

    @pytest.mark.crust
    def test_async_file_operations(self, benchmark, async_dataset):
        """Benchmark async file I/O operations."""

        async def async_file_operations():
            temp_files = []
            try:
                tasks = []
                for i in range(10):
                    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix=f'_async_{i}.txt', delete=False)
                    temp_files.append(temp_file.name)
                    temp_file.close()

                async def write_file(file_path, data):
                    async with aiofiles.open(file_path, 'w') as f:
                        await f.write(str(data))
                for i, file_path in enumerate(temp_files):
                    task = write_file(file_path, async_dataset[i * 100:(i + 1) * 100])
                    tasks.append(task)
                await asyncio.gather(*tasks)
                read_tasks = []

                async def read_file(file_path):
                    async with aiofiles.open(file_path) as f:
                        return await f.read()
                for file_path in temp_files:
                    read_tasks.append(read_file(file_path))
                results = await asyncio.gather(*read_tasks)
                return len(results)
            finally:
                for file_path in temp_files:
                    try:
                        Path(file_path).unlink()
                    except Exception:
                        pass

        def run_async_test():
            return asyncio.run(async_file_operations())
        result = benchmark(run_async_test)
        assert result == 10

    @pytest.mark.crust
    def test_async_concurrent_operations(self, benchmark):
        """Benchmark concurrent async operations."""

        async def concurrent_operations():

            async def simulate_db_operation(operation_id: int, delay: float=0.01):
                await asyncio.sleep(delay)
                return {'id': operation_id, 'result': f'operation_{operation_id}_complete'}
            tasks = [simulate_db_operation(i) for i in range(50)]
            results = await asyncio.gather(*tasks)
            return len(results)

        def run_concurrent_test():
            return asyncio.run(concurrent_operations())
        result = benchmark(run_concurrent_test)
        assert result == 50

    @pytest.mark.crust
    def test_async_batch_processing(self, benchmark, async_dataset):
        """Benchmark async batch processing operations."""

        async def batch_processing():
            batch_size = 100

            async def process_batch(batch_data: list[dict]):
                await asyncio.sleep(0.001)
                return len(batch_data)
            tasks = []
            for i in range(0, len(async_dataset), batch_size):
                batch = async_dataset[i:i + batch_size]
                tasks.append(process_batch(batch))
            results = await asyncio.gather(*tasks)
            return sum(results)

        def run_batch_test():
            return asyncio.run(batch_processing())
        result = benchmark(run_batch_test)
        assert result == len(async_dataset)

    @pytest.mark.crust
    def test_asyncio_event_loop_performance(self, benchmark):
        """Benchmark event loop creation and task scheduling."""

        def event_loop_test():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def simple_task(task_id):
                return task_id * 2
            try:
                tasks = [simple_task(i) for i in range(100)]
                results = loop.run_until_complete(asyncio.gather(*tasks))
                return len(results)
            finally:
                loop.close()
        result = benchmark(event_loop_test)
        assert result == 100

    @pytest.mark.crust
    def test_async_queue_performance(self, benchmark):
        """Benchmark async queue operations."""

        async def queue_operations():
            queue = asyncio.Queue(maxsize=1000)

            async def producer():
                for i in range(500):
                    await queue.put(f'item_{i}')

            async def consumer():
                items = []
                for _ in range(500):
                    item = await queue.get()
                    items.append(item)
                    queue.task_done()
                return items
            producer_task = asyncio.create_task(producer())
            consumer_task = asyncio.create_task(consumer())
            await producer_task
            consumed_items = await consumer_task
            return len(consumed_items)

        def run_queue_test():
            return asyncio.run(queue_operations())
        result = benchmark(run_queue_test)
        assert result == 500
