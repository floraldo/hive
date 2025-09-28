# Git Branch Analysis Report

## Executive Summary
- **Current branch**: main
- **Local branches**: 29
- **Remote branches**: 5
- **Merged branches**: 28
- **Stale branches**: 0

## ✅ Safe to Delete (Merged Branches)
These branches have been merged into main and can be safely deleted:

- `+ agent/backend/1323cd3c-3db2-4301-8fde-8c33a80df1bd` - Merged into main
- `agent/backend/565d030e-86ca-4289-abf6-911a6517b0c1` - Merged into main
- `agent/backend/897a6cb0-91ea-41e4-8a68-c52574e38258` - Merged into main
- `agent/backend/ad41d84d-47d1-46af-a776-a9507185ac53` - Merged into main
- `agent/backend/invalid-task-id` - Merged into main
- `+ agent/backend/test` - Merged into main
- `+ agent/backend/test-direct-6a71afd5` - Merged into main
- `+ agent/backend/test-direct-e739beb8` - Merged into main
- `+ agent/backend/test-spawn-68860288` - Merged into main
- `+ agent/backend/test123` - Merged into main
- `+ agent/backend/test_missing` - Merged into main
- `cleanup-before-changes` - Merged into main
- `feature/--%F0%9F%8E%AF-how-the-hive-wo-1757437905` - Merged into main
- `feature/----%E2%9C%85-queen-is-running-1757437930` - Merged into main
- `feature/----%E2%9C%85-tmux-session-wit-1757437938` - Merged into main
- `feature/--current-state%3A-1757437921` - Merged into main
- `feature/--works-and-what-happens-next%-1757437889` - Merged into main
- `feature/-1757437897` - Merged into main
- `feature/-1757437913` - Merged into main
- `feature/excellent-question%21-the-quee-1757437881` - Merged into main
- `feature/please-analyse-our-codebase-an-1757440130` - Merged into main
- `test-branch` - Merged into main
- `test/kiss-approach` - Merged into main
- `test/kiss-clean` - Merged into main
- `worker/backend` - Merged into main
- `worker/frontend` - Merged into main
- `worker/infra` - Merged into main
- `worker/queen` - Merged into main

**Deletion command**:
```bash
git branch -d + agent/backend/1323cd3c-3db2-4301-8fde-8c33a80df1bd
git branch -d agent/backend/565d030e-86ca-4289-abf6-911a6517b0c1
git branch -d agent/backend/897a6cb0-91ea-41e4-8a68-c52574e38258
git branch -d agent/backend/ad41d84d-47d1-46af-a776-a9507185ac53
git branch -d agent/backend/invalid-task-id
git branch -d + agent/backend/test
git branch -d + agent/backend/test-direct-6a71afd5
git branch -d + agent/backend/test-direct-e739beb8
git branch -d + agent/backend/test-spawn-68860288
git branch -d + agent/backend/test123
git branch -d + agent/backend/test_missing
git branch -d cleanup-before-changes
git branch -d feature/--%F0%9F%8E%AF-how-the-hive-wo-1757437905
git branch -d feature/----%E2%9C%85-queen-is-running-1757437930
git branch -d feature/----%E2%9C%85-tmux-session-wit-1757437938
git branch -d feature/--current-state%3A-1757437921
git branch -d feature/--works-and-what-happens-next%-1757437889
git branch -d feature/-1757437897
git branch -d feature/-1757437913
git branch -d feature/excellent-question%21-the-quee-1757437881
git branch -d feature/please-analyse-our-codebase-an-1757440130
git branch -d test-branch
git branch -d test/kiss-approach
git branch -d test/kiss-clean
git branch -d worker/backend
git branch -d worker/frontend
git branch -d worker/infra
git branch -d worker/queen
```

## 🟢 Active Branches (Recent Activity)
These branches have recent commits:

- `+ agent/backend/1323cd3c-3db2-4301-8fde-8c33a80df1bd` - 0 days old
- `+ agent/backend/test` - 0 days old
- `+ agent/backend/test-direct-6a71afd5` - 0 days old
- `+ agent/backend/test-direct-e739beb8` - 0 days old
- `+ agent/backend/test-spawn-68860288` - 0 days old
- ... and 27 more

## 📋 Branch Naming Analysis

### Feature Branches (9)
- `feature/--%F0%9F%8E%AF-how-the-hive-wo-1757437905`
- `feature/----%E2%9C%85-queen-is-running-1757437930`
- `feature/----%E2%9C%85-tmux-session-wit-1757437938`
- `feature/--current-state%3A-1757437921`
- `feature/--works-and-what-happens-next%-1757437889`
- ... and 4 more

### Agent Branches (4)
- `agent/backend/565d030e-86ca-4289-abf6-911a6517b0c1`
- `agent/backend/897a6cb0-91ea-41e4-8a68-c52574e38258`
- `agent/backend/ad41d84d-47d1-46af-a776-a9507185ac53`
- `agent/backend/invalid-task-id`

### Worker Branches (7)
- `worker/backend`
- `worker/frontend`
- `worker/infra`
- `worker/queen`
- `worker/backend`
- ... and 2 more

### Test Branches (3)
- `test-branch`
- `test/kiss-approach`
- `test/kiss-clean`

### Cleanup Branches (1)
- `cleanup-before-changes`

### Other Branches (9)
- `+ agent/backend/1323cd3c-3db2-4301-8fde-8c33a80df1bd`
- `+ agent/backend/test`
- `+ agent/backend/test-direct-6a71afd5`
- `+ agent/backend/test-direct-e739beb8`
- `+ agent/backend/test-spawn-68860288`
- ... and 4 more

## 🎯 Recommendations

### Immediate Actions
1. **Delete 28 merged branches** - Zero risk, immediate cleanup

### Naming Cleanup
3. **Clean up agent branch naming** - Some branches have complex/invalid names

## ✅ Execution Plan
1. **Phase 1**: Delete merged branches (zero risk)
2. **Phase 2**: Review stale branches with team
3. **Phase 3**: Standardize branch naming conventions
