---
id: com.scm.ProjectAW#createProject
name: createProject
category: scm/project
description: 创建一个新的项目

---

# Action Word: createProject

## 1. 核心意图 (Intent & Keywords)

> 关键词: 项目, 创建, 新建
> 场景标签: SCM, Project

**简要描述**:
创建一个新的项目并返回项目ID。

## 2. 接口参数(Parameter)

**是否需人工确认**: 是

| 参数名 (Arg Name) | 类型 (Type) | 必填 (Required) | 默认值 (Default) | 含义与取值说明 (Description) |
| :---------------- | :---------- | :-------------- | :--------------- | :--------------------------- |
| `name`            | String      | 是              | -                | 项目名称                     |
| `owner`           | String      | 否              | -                | 负责人用户名                 |

## 3. 逻辑约束 (Constraints)

- **前置条件 (Pre-condition)**:
  - [ ] 页面必须停留在: `项目列表页`
  - [ ] 登录状态要求: `已登录`
  - [ ] 上下文依赖: 无
- **后置结果 (Post-condition)**:
  - 成功: 创建成功并返回项目ID
  - 失败: 如果失败，通常是因为 `项目名称冲突`

## 4. 调用示例 (Few-Shot Examples)

**用户意图**: "创建一个新项目"
**正确调用**:

```python
createProject(
    name="demo-project",
    owner="alice"
)
```
