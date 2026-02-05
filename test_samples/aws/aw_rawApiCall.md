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
