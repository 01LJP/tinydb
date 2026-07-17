# Brainstorm Summary

- Change: tinydb-v02
- Date: 2026-07-17

## Confirmed Technical Approach

1. **JOIN**: 嵌套循环连接（Nested-Loop Join），支持 INNER/LEFT/CROSS JOIN，输出列名 `table.column` 格式，多表链式组合
2. **执行器管线**: JOIN 算子插入 SeqScan → Filter 之间，保持迭代器组合式设计
3. **并发控制**: ReadWriteLock + 表级锁粒度，BufferPool threading.Lock，Catalog threading.RLock
4. **CLI**: 纯标准库 readline + ANSI 转义码，EXPLAIN 执行计划树形输出
5. **工作区**: git worktree 隔离，并行开发 join/concurrency/cli 三个分支

## Key Trade-offs and Risks

- 嵌套循环 O(n*m) 性能 → 教学数据库数据量小可接受
- 表级锁并发度有限 → 比数据库级锁好，行级锁留待后续版本
- readline Windows 不兼容 → 主要目标平台 Linux/macOS

## Testing Strategy

- 每个功能模块独立测试文件（test_join.py, test_concurrency.py, test_cli.py）
- 全量回归测试确保 v0.1 功能不受影响
- 端到端集成测试覆盖 JOIN + 并发 + CLI 组合场景

## Spec Patches

None — open 阶段的 delta specs 已覆盖所有需求场景
