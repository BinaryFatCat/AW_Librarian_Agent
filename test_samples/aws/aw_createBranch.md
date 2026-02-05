---
id: com.scm.BranchAW#createBranch
name: createBranch
category: scm/git/branch
description: 在项目中创建分支

---

# Action Word: createBranch

## 1. 核心意图 (Intent & Keywords)

> 关键词: 分支, 创建, 新建, 项目
> 场景标签: SCM, Git, Branch

**简要描述**:
在指定项目中创建一个新的分支。

## 2. 接口参数(Parameter)

**是否需人工确认**: 否

| 参数名 (Arg Name) | 类型 (Type) | 必填 (Required) | 默认值 (Default) | 含义与取值说明 (Description) |
| :---------------- | :---------- | :-------------- | :--------------- | :--------------------------- |
| `pid`             | Long        | 是              | -                | 项目ID                       |
| `branchName`      | String      | 是              | -                | 分支名称                     |

## 3. 逻辑约束 (Constraints)

- **前置条件 (Pre-condition)**:
  - [ ] 页面必须停留在: `项目详情页`
  - [ ] 登录状态要求: `已登录`
  - [ ] 上下文依赖: 项目已存在
- **后置结果 (Post-condition)**:
  - 成功: 分支创建成功
  - 失败: 如果失败，通常是因为 `分支名冲突`

## 4. 调用示例 (Few-Shot Examples)

**用户意图**: "在项目中创建分支"
**正确调用**:

```python
createBranch(
    pid="12345",
    branchName="feature-x"
)
```
