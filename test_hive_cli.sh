#!/bin/bash
# Test script for Hive CLI - validates all commands work correctly

echo "======================================"
echo "🧪 Testing Hive CLI Commands"
echo "======================================"

# Test 1: Help command
echo -e "\n[TEST 1] Testing help command..."
python hive.py --help > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "[PASS] Help command works"
else
    echo "[FAIL] Help command failed"
    exit 1
fi

# Test 2: Init command (without sample to avoid duplicate)
echo -e "\n[TEST 2] Testing init command..."
python hive.py init > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "[PASS] Init command works"
else
    echo "[FAIL] Init command failed"
    exit 1
fi

# Test 3: Task queue (should show existing tasks)
echo -e "\n[TEST 3] Testing task:queue command..."
python hive.py task:queue > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "[PASS] Task queue command works"
else
    echo "[FAIL] Task queue command failed"
    exit 1
fi

# Test 4: Add a test task
echo -e "\n[TEST 4] Testing task:add command..."
python hive.py task:add --id test_cli_002 --title "CLI Test Task" --description "Testing CLI functionality" --tags test cli --priority P3 --risk low > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "[PASS] Task add command works"
else
    echo "[FAIL] Task add command failed"
    exit 1
fi

# Test 5: View the test task
echo -e "\n[TEST 5] Testing task:view command..."
python hive.py task:view --id test_cli_002 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "[PASS] Task view command works"
else
    echo "[FAIL] Task view command failed"
    exit 1
fi

# Test 6: Set a hint
echo -e "\n[TEST 6] Testing hint:set command..."
python hive.py hint:set --id test_cli_002 --text "This is a test hint" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "[PASS] Hint set command works"
else
    echo "[FAIL] Hint set command failed"
    exit 1
fi

# Test 7: Clear the hint
echo -e "\n[TEST 7] Testing hint:clear command..."
python hive.py hint:clear --id test_cli_002 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "[PASS] Hint clear command works"
else
    echo "[FAIL] Hint clear command failed"
    exit 1
fi

# Test 8: Set an interrupt
echo -e "\n[TEST 8] Testing interrupt:set command..."
python hive.py interrupt:set --id test_cli_002 --reason "Testing interrupt functionality" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "[PASS] Interrupt set command works"
else
    echo "[FAIL] Interrupt set command failed"
    exit 1
fi

# Test 9: Clear the interrupt
echo -e "\n[TEST 9] Testing interrupt:clear command..."
python hive.py interrupt:clear --id test_cli_002 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "[PASS] Interrupt clear command works"
else
    echo "[FAIL] Interrupt clear command failed"
    exit 1
fi

# Test 10: Test command parsing (should fail gracefully for invalid commands)
echo -e "\n[TEST 10] Testing invalid command handling..."
python hive.py invalid_command > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "[PASS] Invalid command handling works"
else
    echo "[FAIL] Invalid command should have failed"
    exit 1
fi

echo -e "\n======================================"
echo "✅ All CLI tests passed!"
echo "======================================"

echo -e "\nCLI is ready for use. Example commands:"
echo "  python hive.py init --sample"
echo "  python hive.py task:queue"
echo "  python hive.py queen"
echo "  python hive.py status"
echo "  python hive.py events:tail"
echo ""
echo "For full help: python hive.py --help"