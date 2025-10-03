# Conda Hive Environment Setup

## Purpose

Set up `hive` conda environment as default bash environment with Python 3.11

## Current State

- **Bash default**: smarthoods_agency (Python 3.10.16)
- **Poetry virtualenv**: Python 3.11.9 ✅ (already correct)
- **Desired**: hive (Python 3.11) as bash default

## Setup Instructions

### Step 1: Create Hive Conda Environment

**Option A: Manual (if background process didn't complete)**
```bash
conda create -n hive python=3.11 -y
```

**Option B: Verify if already created**
```bash
conda env list | grep hive
```

### Step 2: Configure Bash to Use Hive by Default

**For Git Bash (Windows)**

Edit `~/.bashrc`:
```bash
# Add this at the end of ~/.bashrc
# Auto-activate hive conda environment
if [ -z "$CONDA_DEFAULT_ENV" ] || [ "$CONDA_DEFAULT_ENV" = "base" ]; then
    source "/c/Users/flori/Anaconda/etc/profile.d/conda.sh"
    conda activate hive
fi
```

**For PowerShell**

Edit PowerShell profile:
```powershell
# Find profile location
echo $PROFILE

# Add to profile
conda activate hive
```

### Step 3: Verify Setup

```bash
# Open NEW bash terminal
python --version  # Should show Python 3.11.x

# Verify conda env
conda env list    # Should show * next to hive
```

## Alternative: Pure Poetry (Recommended)

If you prefer **no conda at all**, just always use poetry:

```bash
# Instead of configuring bash default, just use poetry run
poetry run python --version   # 3.11.9
poetry run ruff check .
poetry run pytest
```

## Why This Matters

### Problem We're Solving
- Terminal defaulting to smarthoods_agency (Python 3.10)
- Hive project requires Python ^3.11
- Want consistent Python version in bash

### Impact
- ✅ Formatters (ruff/black) run with Python 3.11
- ✅ Tests run with correct Python version
- ✅ No more mixing Python 3.10 and 3.11 environments

## Verification Commands

After setup:
```bash
# Check Python version
python --version          # Should be 3.11.x

# Check active conda env
echo $CONDA_DEFAULT_ENV   # Should be "hive"

# Check where Python is from
which python              # Should point to Anaconda/envs/hive/

# Poetry still works independently
poetry run python --version  # Still 3.11.9 (virtualenv)
```

## Troubleshooting

### Conda env creation is slow
**Normal** - conda package resolution can take 5-10 minutes

### Already have hive env
```bash
# Check if it exists
conda env list

# If it exists, just activate it
conda activate hive
```

### Can't modify .bashrc
```bash
# Find your .bashrc
ls -la ~ | grep bashrc

# Edit with nano or vim
nano ~/.bashrc
# OR
vim ~/.bashrc
```

## Recommendation

**For pure poetry workflow (preferred)**:
- Skip conda env setup entirely
- Always use `poetry run <command>`
- Poetry handles Python 3.11 correctly

**For bash convenience**:
- Complete conda hive env setup
- Get Python 3.11 as default in bash
- Poetry still works independently
