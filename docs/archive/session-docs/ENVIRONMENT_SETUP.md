# Hive Platform Environment Setup

**Quick Start**: Create dedicated `hive` conda environment with Python 3.11

---

## Why a Dedicated Environment?

- **Isolated from other projects** (smarthoods_agency, main, etc.)
- **Python 3.11 required** (26/26 packages need 3.11+)
- **Clean dependency management** (no conflicts with other repos)

---

## One-Command Setup

### Option 1: Automated Script (Recommended)

```bash
# From Git Bash or WSL
cd /c/git/hive
bash scripts/setup_hive_environment.sh
```

**What it does**:
1. Creates `hive` conda environment with Python 3.11
2. Activates the environment
3. Installs Poetry
4. Configures Poetry to use conda env
5. Installs all project dependencies

**Time**: ~5-10 minutes (depending on download speed)

---

## Manual Setup (If Script Fails)

### Step 1: Create Environment

```bash
conda create -n hive python=3.11 -y
```

### Step 2: Activate

```bash
conda activate hive
```

### Step 3: Install Poetry

```bash
pip install poetry
```

### Step 4: Configure Poetry

```bash
poetry config virtualenvs.create false
```

### Step 5: Install Dependencies

```bash
cd /c/git/hive/apps/ecosystemiser
poetry install
```

---

## Verification

After setup, verify everything works:

```bash
# 1. Check Python version
python --version
# Expected: Python 3.11.x

# 2. Check conda environment
conda env list | grep hive
# Expected: hive                     *  /c/Users/flori/Anaconda/envs/hive

# 3. Test hive-db import
python -c "from hive_db import get_sqlite_connection; print('SUCCESS')"
# Expected: SUCCESS

# 4. Run database validation
cd /c/git/hive/apps/ecosystemiser
python scripts/validate_database_logging.py
# Expected: [OK] All validation tests passed!
```

---

## Using the Environment

### Command Line

```bash
# Activate environment
conda activate hive

# Your prompt should change to show (hive) prefix
# (hive) user@machine:~/path$

# Run commands
python your_script.py
poetry run pytest
```

### VSCode

1. Open Command Palette (`Ctrl+Shift+P`)
2. Search: "Python: Select Interpreter"
3. Choose: `Python 3.11.x ('hive')`
   - Path: `C:\Users\flori\Anaconda\envs\hive\python.exe`

### PyCharm

1. File → Settings → Project → Python Interpreter
2. Click gear icon → Add
3. Conda Environment → Existing environment
4. Select: `C:\Users\flori\Anaconda\envs\hive\python.exe`

---

## Troubleshooting

### Conda Not Found

**Error**: `conda: command not found`

**Fix**: Add Anaconda to PATH or use full path:

```bash
# Option A: Add to PATH (recommended)
export PATH="/c/Users/flori/Anaconda/Scripts:$PATH"

# Option B: Use full path
/c/Users/flori/Anaconda/Scripts/conda.exe create -n hive python=3.11 -y
```

### Poetry Install Fails

**Error**: `Current Python version (3.10.16) is not allowed`

**Fix**: Ensure `hive` environment is activated:

```bash
conda activate hive
python --version  # Should show 3.11.x
poetry install
```

### Import Errors After Setup

**Error**: `ModuleNotFoundError: No module named 'hive_db'`

**Fix**: Reinstall dependencies in correct environment:

```bash
conda activate hive
cd /c/git/hive/apps/ecosystemiser
poetry install --no-cache
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Activate environment | `conda activate hive` |
| Deactivate environment | `conda deactivate` |
| List environments | `conda env list` |
| Check Python version | `python --version` |
| Install dependencies | `poetry install` |
| Update dependencies | `poetry update` |
| Run tests | `poetry run pytest` |
| Delete environment | `conda env remove -n hive` |

---

## Environment Details

**Name**: `hive`
**Python**: 3.11.x
**Location**: `~/Anaconda/envs/hive/`
**Package Manager**: Poetry
**Dependencies**: Managed via `pyproject.toml` in each package

---

## Next Steps After Setup

1. **Activate environment**: `conda activate hive`
2. **Verify Phase 1**: `cd /c/git/hive/apps/ecosystemiser && python scripts/validate_database_logging.py`
3. **Run tests**: `poetry run pytest tests/integration/test_database_logging.py`
4. **Start development**: You're ready for Phase 2!

---

**Status**: Ready to create `hive` environment
**Scripts**: `scripts/setup_hive_environment.sh` (bash) or `scripts/setup_hive_environment.bat` (Windows CMD)
