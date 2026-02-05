---
id: com.scm.GitAW#listBranchesByProjectId
name: listBranchesByProjectId
category: scm/git/branch
description: 根据项目ID获取分支列表
---

# Action Word: listBranchesByProjectId

## 1. 核心意图 (Intent & Keywords)

> 关键词: 项目, 分支, 列表, 获取, 查询
> 场景标签: SCM, Git, Branch

**简要描述**:
通过项目ID查询该项目下的全部分支列表。

## 2. 接口参数(Parameter)

**是否需人工确认**: 否

| 参数名 (Arg Name) | 类型 (Type) | 必填 (Required) | 默认值 (Default) | 含义与取值说明 (Description) |
| :---------------- | :---------- | :-------------- | :--------------- | :--------------------------- |
| `pid`             | Long        | 是              | -                | 项目ID                       |

## 3. 逻辑约束 (Constraints)

- **前置条件 (Pre-condition)**:
  - [ ] 页面必须停留在: `项目详情页`
  - [ ] 登录状态要求: `已登录`
  - [ ] 上下文依赖: 项目已存在
- **后置结果 (Post-condition)**:
  - 成功: 返回分支列表
  - 失败: 如果失败，通常是因为 `项目不存在`

## 4. 调用示例 (Few-Shot Examples)

**用户意图**: "获取项目的分支列表"
**正确调用**:

```python
listBranchesByProjectId(
    pid="12345"
)
```
