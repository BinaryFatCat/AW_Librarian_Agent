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

---

id: com.internal.HelperAW#rawApiCall
name: rawApiCall
category: internal/helper
description: 通用API直调

---

# Action Word: rawApiCall

## 1. 核心意图 (Intent & Keywords)

> 关键词: 通用, API, 直调, 请求
> 场景标签: Helper, Fallback

**简要描述**:
用于在没有专用AW时进行API直调。

## 2. 接口参数(Parameter)

**是否需人工确认**: 否

| 参数名 (Arg Name) | 类型 (Type) | 必填 (Required) | 默认值 (Default) | 含义与取值说明 (Description) |
| :---------------- | :---------- | :-------------- | :--------------- | :--------------------------- |
| `url`             | String      | 是              | -                | 请求URL                      |
| `method`          | String      | 否              | GET              | HTTP方法                     |
| `payload`         | String      | 否              | -                | 请求体内容                   |

## 3. 逻辑约束 (Constraints)

- **前置条件 (Pre-condition)**:
  - [ ] 页面必须停留在: `任意`
  - [ ] 登录状态要求: `已登录`
  - [ ] 上下文依赖: 无
- **后置结果 (Post-condition)**:
  - 成功: 返回API响应
  - 失败: 如果失败，通常是因为 `接口不可用`

## 4. 调用示例 (Few-Shot Examples)

**用户意图**: "调用通用API"
**正确调用**:

```python
rawApiCall(
    url="https://api.example.com/branches",
    method="GET"
)
```

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

---

id: com.scm.BranchAW#deleteBranch
name: deleteBranch
category: scm/git/branch
description: 删除项目分支

---

# Action Word: deleteBranch

## 1. 核心意图 (Intent & Keywords)

> 关键词: 分支, 删除, 清理, 项目
> 场景标签: SCM, Git, Branch

**简要描述**:
删除指定项目下的分支。

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
  - 成功: 分支删除成功
  - 失败: 如果失败，通常是因为 `分支不存在`

## 4. 调用示例 (Few-Shot Examples)

**用户意图**: "删除项目分支"
**正确调用**:

```python
deleteBranch(
  pid="12345",
  branchName="feature-x"
)
```

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
