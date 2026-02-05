---
id: com.scm.GitAW#getBranchesByName
name: getBranchesByName
category: scm/git/branch
description: 根据项目名称获取分支列表

---

# Action Word: getBranchesByName

## 1. 核心意图 (Intent & Keywords)

> 关键词: 项目名称, 分支, 列表, 获取, 查询
> 场景标签: SCM, Git, Branch

**简要描述**:
通过项目名称查询该项目下的全部分支列表。

## 2. 接口参数(Parameter)

**是否需人工确认**: 否

| 参数名 (Arg Name) | 类型 (Type) | 必填 (Required) | 默认值 (Default) | 含义与取值说明 (Description) |
| :---------------- | :---------- | :-------------- | :--------------- | :--------------------------- |
| `pName`           | String      | 是              | -                | 项目名称                     |

## 3. 逻辑约束 (Constraints)

- **前置条件 (Pre-condition)**:
  - [ ] 页面必须停留在: `项目列表页`
  - [ ] 登录状态要求: `已登录`
  - [ ] 上下文依赖: 项目已存在
- **后置结果 (Post-condition)**:
  - 成功: 返回分支列表
  - 失败: 如果失败，通常是因为 `项目不存在`

## 4. 调用示例 (Few-Shot Examples)

**用户意图**: "通过项目名称获取分支列表"
**正确调用**:

```python
getBranchesByName(
    pName="demo-project"
)
```
