---
id: {{AW_ID}}
name: {{AW_NAME}}
category: {{AW_CATEGORY_PATH}}
description: {{AW_DESCRIPTION}}
---

# Action Word: {{AW_NAME}}

## 1. 核心意图 (Intent & Keywords)
> 关键词: {{KEYWORDS_LIST}}
> 场景标签: {{TAGS}}

**简要描述**:
{{DESCRIPTION_TEXT}}

## 2. 接口参数(Parameter)
**是否需人工确认**: {{BOOLEAN}}

| 参数名 (Arg Name) | 类型 (Type) | 必填 (Required) | 默认值 (Default) | 含义与取值说明 (Description) |
| :---------------- | :---------- | :-------------- | :--------------- | :--------------------------- |
| `{{PARAM_1}}`     | {{TYPE}}    | 是/否           | {{DEFAULT}}      | {{DESC}}                     |
| `{{PARAM_2}}`     | {{TYPE}}    | 是/否           | {{DEFAULT}}      | {{DESC}}                     |

## 3. 逻辑约束 (Constraints)
* **前置条件 (Pre-condition)**:
    - [ ] 页面必须停留在: `{{PAGE_NAME}}`
    - [ ] 登录状态要求: `{{LOGIN_STATE}}`
    - [ ] 上下文依赖: {{DEPENDENCY_DESC}}
* **后置结果 (Post-condition)**:
    - 成功: 页面跳转至 `{{NEXT_PAGE}}` 或 弹出 `{{SUCCESS_MSG}}`
    - 失败: 如果失败，通常是因为 `{{FAILURE_REASON}}`

## 4. 调用示例 (Few-Shot Examples)
**用户意图**: "{{USER_INTENT_EXAMPLE}}"
**正确调用**:
```python
{{AW_NAME}}(
    {{PARAM_1}}="{{VALUE_1}}",
    {{PARAM_2}}="{{VALUE_2}}"
)