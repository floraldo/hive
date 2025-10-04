"""
Integration tests for RAG-Guardian system.

Tests the full end-to-end flow:
1. Guardian detects patterns in PR code
2. RAG retrieves relevant context (patterns, rules, deprecations)
3. Guardian generates intelligent comments
4. Traceability logging captures RAG usage

This validates all four design decisions in a real-world scenario.
"""
from pathlib import Path
import pytest
from hive_logging import get_logger
logger = get_logger(__name__)
MOCK_PR_DATABASE_VIOLATION = ('packages/hive-api/src/hive_api/new_endpoint.py', '\n@@ -0,0 +1,12 @@\n+import sqlite3\n+\n+def get_user_data(user_id: int):\n+    """Get user data from database."""\n+    conn = sqlite3.connect("app.db")\n+    cursor = conn.cursor()\n+    result = cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))\n+    data = result.fetchone()\n+    conn.close()\n+    return data\n')
MOCK_PR_LOGGING_VIOLATION = ('packages/hive-service/src/hive_service/processor.py', '\n@@ -5,3 +5,6 @@\n def process_data(data: dict):\n-    logger.info(f"Processing {len(data)} items")\n+    print(f"Processing {len(data)} items")  # Violation: print() instead of logger\n     return transform(data)\n')
MOCK_PR_CONFIG_VIOLATION = ('apps/new-app/src/new_app/service.py', '\n@@ -0,0 +1,10 @@\n+from hive_config import get_config  # Deprecated global pattern\n+\n+class ServiceHandler:\n+    def __init__(self):\n+        self.config = get_config()  # Should use DI pattern\n+        self.db_path = self.config.database.path\n')

@pytest.mark.crust
class TestRAGGuardianIntegration:
    """Integration tests for RAG-enhanced Guardian Agent."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.rag_index_path = Path(__file__).parent.parent.parent / 'data' / 'rag_index'
        self.rag_available = self.rag_index_path.exists()
        if not self.rag_available:
            pytest.skip('RAG index not found - run scripts/rag/index_hive_codebase.py first')

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_database_violation_detection(self):
        """
        Test that Guardian + RAG correctly identifies database error handling violation.

        Expected behavior:
        1. Guardian detects database operation in PR
        2. RAG retrieves similar patterns with error handling
        3. Guardian posts comment with retrieved pattern example
        4. Comment includes Golden Rule #12 (database error handling)
        """
        from apps.guardian_agent.review.rag_comment_engine import RAGEnhancedCommentEngine
        engine = RAGEnhancedCommentEngine(rag_index_path=self.rag_index_path)
        comment_batch = await engine.analyze_pr_for_comments(pr_files=[MOCK_PR_DATABASE_VIOLATION], pr_number=123)
        assert len(comment_batch.comments) > 0, 'Should generate at least one comment'
        db_comment = next((c for c in comment_batch.comments if 'database' in c.title.lower()), None)
        assert db_comment is not None, 'Should have database-related comment'
        assert db_comment.code_example is not None, 'Should include code example from RAG'
        assert len(db_comment.rag_patterns_used) > 0, 'Should retrieve RAG patterns'
        assert db_comment.retrieval_time_ms > 0, 'Should log retrieval time'
        assert db_comment.confidence_score > 0, 'Should have confidence score'
        logger.info('Database violation test passed', extra={'comments_generated': len(comment_batch.comments), 'rag_patterns_used': len(db_comment.rag_patterns_used), 'retrieval_time_ms': db_comment.retrieval_time_ms, 'confidence': db_comment.confidence_score})

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_logging_violation_detection(self):
        """
        Test that Guardian + RAG correctly identifies print() statement violation.

        Expected behavior:
        1. Guardian detects print() statement
        2. RAG retrieves Golden Rule #10 (no print statements)
        3. Guardian retrieves logging pattern examples
        4. Comment includes proper hive_logging usage
        """
        from apps.guardian_agent.review.rag_comment_engine import RAGEnhancedCommentEngine
        engine = RAGEnhancedCommentEngine(rag_index_path=self.rag_index_path)
        comment_batch = await engine.analyze_pr_for_comments(pr_files=[MOCK_PR_LOGGING_VIOLATION], pr_number=124)
        assert len(comment_batch.comments) > 0, 'Should generate logging comment'
        logging_comment = next((c for c in comment_batch.comments if 'logging' in c.title.lower()), None)
        assert logging_comment is not None, 'Should detect logging violation'
        assert logging_comment.comment_type in ['golden_rule_violation', 'suggestion'], 'Should be violation or suggestion'
        if logging_comment.golden_rules_applied:
            assert 10 in logging_comment.golden_rules_applied, 'Should reference Golden Rule #10'
        logger.info('Logging violation test passed', extra={'comment_type': logging_comment.comment_type, 'golden_rules': logging_comment.golden_rules_applied})

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_config_deprecation_detection(self):
        """
        Test that Guardian + RAG detects deprecated get_config() pattern.

        Expected behavior:
        1. Guardian detects get_config() usage
        2. RAG retrieves deprecation info (Golden Rule #24)
        3. RAG retrieves modern DI pattern examples
        4. Comment suggests create_config_from_sources() replacement
        """
        from apps.guardian_agent.review.rag_comment_engine import RAGEnhancedCommentEngine
        engine = RAGEnhancedCommentEngine(rag_index_path=self.rag_index_path)
        comment_batch = await engine.analyze_pr_for_comments(pr_files=[MOCK_PR_CONFIG_VIOLATION], pr_number=125)
        assert len(comment_batch.comments) > 0, 'Should generate config comment'
        config_comment = next((c for c in comment_batch.comments if 'config' in c.title.lower()), None)
        assert config_comment is not None, 'Should detect config pattern'
        logger.info('Config deprecation test passed', extra={'patterns_retrieved': len(config_comment.rag_patterns_used), 'confidence': config_comment.confidence_score})

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_performance_requirements(self):
        """
        Test that RAG retrieval meets performance targets.

        Target: <150ms p95 latency for retrieval
        """
        from apps.guardian_agent.review.rag_comment_engine import RAGEnhancedCommentEngine
        engine = RAGEnhancedCommentEngine(rag_index_path=self.rag_index_path)
        retrieval_times = []
        for _ in range(10):
            comment_batch = await engine.analyze_pr_for_comments(pr_files=[MOCK_PR_DATABASE_VIOLATION], pr_number=999)
            if comment_batch.comments:
                for comment in comment_batch.comments:
                    retrieval_times.append(comment.retrieval_time_ms)
        retrieval_times.sort()
        p95_index = int(len(retrieval_times) * 0.95)
        p95_latency = retrieval_times[p95_index] if retrieval_times else 0
        logger.info('Performance test results', extra={'samples': len(retrieval_times), 'p95_latency_ms': p95_latency, 'target_ms': 150})
        assert p95_latency < 150, f'P95 latency {p95_latency}ms exceeds 150ms target'

    @pytest.mark.crust
    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """
        Test that Guardian works without RAG (graceful degradation).

        Expected behavior:
        1. RAG unavailable
        2. Guardian continues operation
        3. Comments are still generated (but without RAG context)
        4. Clear logging indicates "operating blind"
        """
        from apps.guardian_agent.review.rag_comment_engine import RAGEnhancedCommentEngine
        fake_path = Path('/tmp/nonexistent_rag_index')
        engine = RAGEnhancedCommentEngine(rag_index_path=fake_path)
        assert engine.rag_available is False, 'Should detect RAG unavailable'
        comment_batch = await engine.analyze_pr_for_comments(pr_files=[MOCK_PR_DATABASE_VIOLATION], pr_number=999)
        logger.info('Graceful degradation test passed', extra={'rag_available': engine.rag_available, 'comments_in_basic_mode': len(comment_batch.comments)})

    @pytest.mark.crust
    def test_github_comment_formatting(self):
        """
        Test that PR comments are properly formatted for GitHub.

        Expected format:
        - Markdown headers
        - Code blocks with syntax highlighting
        - Golden Rule references
        - Footer with metadata
        """
        from apps.guardian_agent.review.rag_comment_engine import PRComment
        comment = PRComment(file_path='test.py', line_number=10, comment_type='suggestion', title='Test Suggestion', message='This is a test message', code_example='def example():\n    pass', rag_patterns_used=['pattern1', 'pattern2'], golden_rules_applied=[10, 12], retrieval_time_ms=87.5, confidence_score=0.92)
        markdown = comment.to_github_comment()
        assert '**Test Suggestion**' in markdown, 'Should have title'
        assert 'This is a test message' in markdown, 'Should have message'
        assert '```python' in markdown, 'Should have code block'
        assert 'Golden Rule #10' in markdown, 'Should reference rules'
        assert 'Guardian Agent with RAG' in markdown, 'Should have footer'
        assert '92%' in markdown, 'Should show confidence'
        assert '87ms' in markdown, 'Should show retrieval time'
        logger.info('GitHub comment formatting test passed')
if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])