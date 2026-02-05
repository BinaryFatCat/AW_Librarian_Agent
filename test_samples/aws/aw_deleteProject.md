---
id: com.scm.ProjectAW#deleteProject
name: deleteProject
category: scm/project
description: 删除一个项目

---

# Action Word: deleteProject

## 1. 核心意图 (Intent & Keywords)

> 关键词: 项目, 删除, 清理, 回收
> 场景标签: SCM, Project

**简要描述**:
删除指定项目并清理相关资源。

## 2. 接口参数(Parameter)

**是否需人工确认**: 是

| 参数名 (Arg Name) | 类型 (Type) | 必填 (Required) | 默认值 (Default) | 含义与取值说明 (Description) |
| :---------------- | :---------- | :-------------- | :--------------- | :--------------------------- |
| `pid`             | Long        | 是              | -                | 项目ID                       |
| `force`           | Boolean     | 否              | false            | 是否强制删除                 |

## 3. 逻辑约束 (Constraints)

- **前置条件 (Pre-condition)**:
  - [ ] 页面必须停留在: `项目详情页`
  - [ ] 登录状态要求: `已登录`
  - [ ] 上下文依赖: 项目已存在
- **后置结果 (Post-condition)**:
  - 成功: 项目被删除
  - 失败: 如果失败，通常是因为 `项目不存在`

## 4. 调用示例 (Few-Shot Examples)

**用户意图**: "删除项目"
**正确调用**:

```python
deleteProject(
  pid="12345",
  force="false"
)
```
