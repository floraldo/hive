"""Demonstration of RAG-Enhanced PR Comment Engine.

This shows how the Guardian Agent uses RAG to post intelligent,
contextual comments on pull requests WITHOUT modifying code.

This is the SAFE read-only integration approach.
"""

import asyncio

# Mock PR data
MOCK_PR_FILES = [
    (
        "packages/hive-db/src/hive_db/new_feature.py",
        '''@@ -0,0 +1,15 @@
+def execute_query(query: str):
+    """Execute database query."""
+    connection = sqlite3.connect("database.db")
+    cursor = connection.cursor()
+    result = cursor.execute(query)
+    data = result.fetchall()
+    connection.close()
+    return data
''',
    ),
    (
        "packages/hive-api/src/hive_api/endpoint.py",
        """
@@ -10,5 +10,8 @@
 def process_request(data: dict):
-    config = get_config()  # Old global pattern
+    print(f"Processing: {data}")  # Logging violation
+    config = get_config()
     return process_data(config, data)
""",
    ),
]


async def demo_rag_comments():
    """Demonstrate RAG-enhanced PR comments."""
    print("=" * 60)
    print("Guardian Agent - RAG-Enhanced PR Comment Demo")
    print("=" * 60)
    print()
    print("Analyzing mock PR with 2 files...")
    print()

    # Note: This would normally import RAGEnhancedCommentEngine
    # For demo purposes, we'll show what the output would look like

    print("File 1: packages/hive-db/src/hive_db/new_feature.py")
    print("-" * 60)
    print()
    print("**Database Operation Suggestion**")
    print()
    print(
        "Similar database operations in the codebase use async context managers "
        "with proper error handling. Consider adding similar error handling here for resilience.",
    )
    print()
    print("**Example Pattern:**")
    print("```python")
    print("async with self.pool.get_connection() as conn:")
    print("    try:")
    print("        result = await conn.execute(query)")
    print("    except sqlite3.Error as e:")
    print("        logger.error(f'Database error: {e}')")
    print("        raise")
    print("```")
    print()
    print("**Applicable Golden Rules:**")
    print("- Golden Rule #12: All database operations must have proper error handling")
    print()
    print("---")
    print(
        "*Guardian Agent with RAG • Confidence: 92% • Retrieved: 2 patterns in 87ms*",
    )
    print()
    print()

    print("File 2: packages/hive-api/src/hive_api/endpoint.py")
    print("-" * 60)
    print()
    print("**Logging Best Practice**")
    print()
    print(
        "The codebase uses `hive_logging.get_logger(__name__)` for all logging. "
        "Avoid using `print()` statements. Use structured logging instead.",
    )
    print()
    print("**Example Pattern:**")
    print("```python")
    print("from hive_logging import get_logger")
    print()
    print("logger = get_logger(__name__)")
    print("logger.info('Processing request', extra={'data': data})")
    print("```")
    print()
    print("**Applicable Golden Rules:**")
    print("- Golden Rule #10: No print() statements - Use hive_logging.get_logger()")
    print()
    print("---")
    print(
        "*Guardian Agent with RAG • Confidence: 95% • Retrieved: 3 patterns in 45ms*",
    )
    print()
    print()

    print("=" * 60)
    print("Guardian RAG Review Summary:")
    print("- Files Analyzed: 2")
    print("- Suggestions: 2")
    print("- Golden Rule Violations: 2")
    print("- Deprecation Warnings: 0")
    print("- Total RAG Retrieval Time: 132ms")
    print("=" * 60)
    print()
    print(
        "✅ Comments posted to PR #123. No code was modified (read-only operation).",
    )
    print()


if __name__ == "__main__":
    asyncio.run(demo_rag_comments())
