---
id: com.scm.BranchAW#listBranchesWithStatus
name: listBranchesWithStatus
category: scm/git/branch
description: 获取分支列表并包含状态

---

# Action Word: listBranchesWithStatus

## 1. 核心意图 (Intent & Keywords)

> 关键词: 分支, 列表, 状态, 获取
> 场景标签: SCM, Git, Branch

**简要描述**:
获取项目分支列表，并返回每个分支的状态信息。

## 2. 接口参数(Parameter)

**是否需人工确认**: 否

| 参数名 (Arg Name) | 类型 (Type) | 必填 (Required) | 默认值 (Default) | 含义与取值说明 (Description) |
| :---------------- | :---------- | :-------------- | :--------------- | :--------------------------- |
| `pid`             | Long        | 是              | -                | 项目ID                       |
| `status`          | String      | 否              | ALL              | 分支状态过滤条件             |

## 3. 逻辑约束 (Constraints)

- **前置条件 (Pre-condition)**:
  - [ ] 页面必须停留在: `项目详情页`
  - [ ] 登录状态要求: `已登录`
  - [ ] 上下文依赖: 项目已存在
- **后置结果 (Post-condition)**:
  - 成功: 返回包含状态的分支列表
  - 失败: 如果失败，通常是因为 `项目不存在`

## 4. 调用示例 (Few-Shot Examples)

**用户意图**: "获取包含状态的分支列表"
**正确调用**:

```python
listBranchesWithStatus(
  pid="12345",
  status="ACTIVE"
)
```
