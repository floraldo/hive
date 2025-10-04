"""Test YAML and TOML chunking functionality.

Simple script to validate that YAML and TOML files are correctly chunked
for RAG indexing.

Usage:
    python scripts/rag/test_config_chunking.py
"""

import sys
from pathlib import Path

# Add hive-ai to path for testing
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "hive-ai" / "src"))


def test_yaml_chunking():
    """Test YAML file chunking."""
    print("=" * 70)
    print("Testing YAML Chunking")
    print("=" * 70)

    # Test with a real workflow file
    workflow_files = list((PROJECT_ROOT / ".github" / "workflows").glob("*.yml"))

    if not workflow_files:
        print("⚠ No workflow files found to test")
        return False

    try:
        # Import after adding to path
        from hive_ai.rag.chunker import HierarchicalChunker

        chunker = HierarchicalChunker()

        for workflow_file in workflow_files[:3]:  # Test first 3
            print(f"\nProcessing: {workflow_file.name}")

            chunks = chunker.chunk_yaml(workflow_file)

            print(f"  Chunks created: {len(chunks)}")

            if chunks:
                print("  Sample chunk:")
                chunk = chunks[0]
                print(f"    Type: {chunk.chunk_type}")
                print(f"    Lines: {chunk.start_line}-{chunk.end_line}")
                print(f"    Metadata: {chunk.metadata}")
                print(f"    Content preview: {chunk.content[:100]}...")

        print("\n✅ YAML chunking test passed")
        return True

    except Exception as e:
        print(f"\n❌ YAML chunking test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_toml_chunking():
    """Test TOML file chunking."""
    print("\n" + "=" * 70)
    print("Testing TOML Chunking")
    print("=" * 70)

    # Test with pyproject.toml
    pyproject_file = PROJECT_ROOT / "pyproject.toml"

    if not pyproject_file.exists():
        print("⚠ pyproject.toml not found to test")
        return False

    try:
        from hive_ai.rag.chunker import HierarchicalChunker

        chunker = HierarchicalChunker()

        print(f"\nProcessing: {pyproject_file.name}")

        chunks = chunker.chunk_toml(pyproject_file)

        print(f"  Chunks created: {len(chunks)}")

        if chunks:
            print("\n  Sample chunks:")
            for i, chunk in enumerate(chunks[:5], 1):  # Show first 5
                table_name = chunk.metadata.get("table", "unknown")
                print(f"    {i}. {table_name}")
                print(f"       Lines: {chunk.start_line}-{chunk.end_line}")
                print(f"       Preview: {chunk.content[:80]}...")

        print("\n✅ TOML chunking test passed")
        return True

    except Exception as e:
        print(f"\n❌ TOML chunking test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main() -> int:
    """Run all configuration chunking tests."""
    print("Configuration File Chunking Tests")
    print("=" * 70)

    # Test YAML
    yaml_ok = test_yaml_chunking()

    # Test TOML
    toml_ok = test_toml_chunking()

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"YAML chunking: {'✅ PASS' if yaml_ok else '❌ FAIL'}")
    print(f"TOML chunking: {'✅ PASS' if toml_ok else '❌ FAIL'}")
    print("=" * 70)

    return 0 if (yaml_ok and toml_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
