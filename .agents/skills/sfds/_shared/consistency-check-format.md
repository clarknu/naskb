# 一致性检查输出格式（共享规范）

> **本文件是 SFDS 全项目一致性检查的单一真相源。** 所有设计/代码 skill 的一致性检查模式
> （consistency-check mode）必须遵循本规范定义的报告结构、`type` 枚举和 `source` 枚举。
> review skill 作为调度器，依赖各 skill 按本规范输出可合并、可统计的结构化报告。

## 1. 报告结构（所有 skill 统一）

所有一致性检查模式输出一份 JSON 报告：

```json
{
  "summary": {
    "end_slug": "{被检查资产的 slug}",
    "total_scanned": 0,
    "total_issues": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  },
  "issues": [
    {
      "severity": "high | medium | low",
      "type": "{见 §2 type 注册表}",
      "source": "{见 §3 source 注册表}",
      "ref_path": "{上游资产定位：文件 + 节点/行}",
      "detail": "{问题具体描述}",
      "suggestion": "{修复建议}"
    }
  ]
}
```

### 字段约定

| 字段 | 必填 | 说明 |
|------|:---:|------|
| `summary.end_slug` | ✅ | 被检查资产的 slug（域或端） |
| `summary.total_issues` | ✅ | 问题总数 |
| `issues[].severity` | ✅ | `high` / `medium` / `low` 三档 |
| `issues[].type` | ✅ | 必须来自 §2 注册表，禁止自造新值 |
| `issues[].source` | ✅ | 必须来自 §3 注册表，标识"上游 → 下游"方向 |
| `issues[].ref_path` | ✅ | 上游产物的精确定位（文件 + 节点），供 review 汇总后直接跳转 |
| `issues[].detail` | ✅ | 问题描述（中文） |
| `issues[].suggestion` | 建议 | 修复建议（中文） |

> **注册表铁律：** 若某 skill 需要新的 `type` 或 `source` 枚举值，必须先在本文档注册，
> 再在 SKILL.md 中引用。禁止 skill 内联自定义枚举造成 review 无法归一化。

## 2. type 注册表

| type | 含义 | 使用方（skill） |
|------|------|----------------|
| `entity_uncovered` | ER 有实体但下游无引用 | entity-relationship, mobile-app-design, desktop-ui-design |
| `field_mismatch` | 字段引用不存在 / 类型不匹配 / 枚举不一致 | entity-relationship, api-design, mobile-app-design, desktop-ui-design |
| `field_missing` | 上游定义了字段但下游遗漏 | entity-relationship, api-design |
| `relationship_orphan` | 关系一端缺失 | entity-relationship |
| `endpoint_uncovered` | 工作流 action 无对应 API 端点 | api-design |
| `endpoint_orphan` | API 端点无工作流依据 | api-design |
| `state_mismatch` | 状态转换与工作流状态机不一致 | api-design, entity-relationship |
| `validation_missing` | 业务校验规则在 API 层缺失 | api-design |
| `workflow_uncovered` | 工作流操作在前端无入口 | mobile-app-design, desktop-ui-design |
| `text_issue` | 文本/i18n 字段缺失或不一致 | mobile-app-design, desktop-ui-design |
| `i18n_key_missing` | i18n key 缺失 | mobile-app-design, desktop-ui-design, mobile-code-gen, desktop-code-gen |
| `perm_ref_missing` | 前端节点缺权限标注 | mobile-app-design, desktop-ui-design |
| `api_call_mismatch` | 前端 API 调用与后端路由/DTO 不一致 | mobile-code-gen, desktop-code-gen, review |
| `design_code_mismatch` | 代码与设计不一致 | api-code-gen, mobile-code-gen, desktop-code-gen |
| `arch_rule_violation` | 分层/模块边界/缓存/可靠性等架构约束违反 | backend-architecture-design, api-code-gen |
| `test_case_missing` | TDD 用例缺失 | tdd-build |
| `assertion_mismatch` | 测试断言与 TDD 设计不一致 | tdd-build |
| `data_flow_broken` | 跨步骤数据流断裂（上游产出下游未接收） | 全部 skill |
| `untraceable` | 无法追溯到原始需求 | 全部 skill |

## 3. source 注册表

`source` 标识一致性检查的方向（上游 → 下游），由执行检查的 skill 声明：

| source | 含义 | 使用方 |
|--------|------|--------|
| `workflow-to-er` | 工作流 → ER | entity-relationship |
| `workflow-to-api` | 工作流 → API | api-design |
| `workflow-to-frontend` | 工作流 → 前端设计 | mobile-app-design, desktop-ui-design |
| `er-to-api` | ER → API | api-design |
| `er-to-orm` | ER → ORM 模型 | api-code-gen |
| `er-to-frontend` | ER → 前端设计 | mobile-app-design, desktop-ui-design |
| `architecture-to-api` | 架构 → API 代码 | backend-architecture-design |
| `architecture-to-code` | 架构 → 代码 | backend-architecture-design |
| `api-to-code` | API 设计 → API 代码 | api-code-gen |
| `design-to-code` | 页面设计 → 页面代码 | mobile-code-gen, desktop-code-gen |
| `code-to-api` | 页面代码 → API 代码（前后端集成） | review（委托 code-gen） |
| `tdd-to-code` | TDD 设计 → 测试代码 | tdd-build |
| `test-to-api` | 测试代码 → API 代码（执行验证） | tdd-execute |

## 4. review 汇总规则

review skill 调度各 skill 的一致性检查模式后，按以下规则合并：

1. 每个 skill 的检查报告作为独立 `{skill}-check` 数据块保留，不混入其他 skill 的问题
2. review 只做问题去重（同 `ref_path` + 同 `type` 视为重复）和严重度排序
3. 报告中的 `type` / `source` 原样保留，review 不做重命名
4. review 新增的问题（如数据流断裂、可追溯性）使用 `source` = `review-*` 前缀的枚举，注册在 review skill 内

## 5. 变更管理

- 修改本文件后，必须同步检查所有引用方 SKILL.md 中的枚举描述是否一致
- 新增枚举必须先在 §2/§3 注册，再被 skill 引用
- 本文件随 `_shared/` 目录整体分发：项目级 `.agents/skills/_shared/` 与全局 `~/.agents/skills/_shared/` 保持同步
