---
id: com.scm.ProjectAW#listProjects
name: listProjects
category: scm/project
description: 获取项目列表

---

# Action Word: listProjects

## 1. 核心意图 (Intent & Keywords)

> 关键词: 项目, 列表, 获取, 查询
> 场景标签: SCM, Project

**简要描述**:
获取当前用户可见的项目列表。

## 2. 接口参数(Parameter)

**是否需人工确认**: 否

| 参数名 (Arg Name) | 类型 (Type) | 必填 (Required) | 默认值 (Default) | 含义与取值说明 (Description) |
| :---------------- | :---------- | :-------------- | :--------------- | :--------------------------- |
| `owner`           | String      | 否              | -                | 负责人用户名过滤             |
| `page`            | Integer     | 否              | 1                | 页码                         |
| `pageSize`        | Integer     | 否              | 20               | 每页数量                     |

## 3. 逻辑约束 (Constraints)

- **前置条件 (Pre-condition)**:
  - [ ] 页面必须停留在: `项目列表页`
  - [ ] 登录状态要求: `已登录`
  - [ ] 上下文依赖: 无
- **后置结果 (Post-condition)**:
  - 成功: 返回项目列表
  - 失败: 如果失败，通常是因为 `权限不足`

## 4. 调用示例 (Few-Shot Examples)

**用户意图**: "获取项目列表"
**正确调用**:

```python
listProjects(
  owner="alice",
  page="1",
  pageSize="20"
)
```
