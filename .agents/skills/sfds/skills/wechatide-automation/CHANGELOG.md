# CHANGELOG — wechatide-automation（仲裁版草稿）

## 2026-08-23 · arb-hub 泛化版 v1

- 泛化自 boxing `wechatide-setup`（inbox/boxing-competition-operation/wechatide-setup@2026-08-23）；保留可复用内容，boxing 专属连接参数/端口/AppID 留在项目实例。

## 2026-08-24 · arb-hub 概念区分（M-04）

- 新增文首「⚠️ 概念区分」：明确 `wechatide-skill` 为 **WeChat IDE 自带的外部工具技能**（不在本 bundle 内，负责根入口 / environment-readiness / automator / wechatide-tools），`wechatide-automation` 为**本方法论扩展**（何时能用 + 怎么接入 SFDS 流水线，drives tdd-execute Stage 2b）；触发词路由、pipeline-registry、development-standard §4 均以 `wechatide-automation` 为准。
- 时序：先修 bundle（M-01~M-06、A1~A10），本技能补「概念区分」；再对齐 tdd-build / tdd-execute §4b。
