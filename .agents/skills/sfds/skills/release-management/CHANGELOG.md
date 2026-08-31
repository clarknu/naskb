# CHANGELOG — release-management（仲裁版草稿）

## 1.2.0-arb.1（2026-08-31，CASE-023/024）

- **§八 增补 #18-20**（源自 consult 2026-08-31 双线部署实践，deployment-config-guide §10.12 同源回收）：
  - #18 对外出口**多线并存**（每线=主域名+公网可达端口+证书+子域→内网端口映射表，互为回退）；**Nginx server 块由「环境参数表+模板+生成器」产出，禁止手写服务器 conf**（配置即代码、资产落库）；80/443 被拦走备用公网端口+通配符证书（acme dns_ali）。
  - #19 **端口收敛三方核对**（容器 compose/宿主监听/云安全组），禁残留公网暴露；公共中间件同样收敛内网。
  - #20 **多环境共主机每环境宿主监听端口必须唯一**（环境参数表独立配置）。
  - #17 微调：与多线模型对齐（Tunnel=并存线而非默认，默认仍直接域名映射）。
- **新增 §九 环境退役/停用（Decommission）**（CASE-024，源自 consult `decommission-old-envs-plan.md` 泛化）：只停服务、不删数据、可随时恢复；红线表（新环境/共享库/他项目/宿主服务不动）；归属勘察三分（本项目停/共享不停/他项目不动）；**处置铁律：先 stop 再逐容器 `docker update --restart=no`（防主机重启复活）**；处置清单=唯一真相源+执行结果留档；对外域名/隧道同步摘除。

## 1.1.0-arb.1（2026-08-30，CASE-014）

- **回流 consult v1.1.0 的 18 条发布教训（§八）**，经 2026-08-30 项目中性审核（`audits/2026-08-30-c014-lessons-review.md`）：A（14 条）全收、B（#12/13/18）收原则、C（#14 Dify 控制台 API 细则）不收、**#18 更正为「Tunnel 非默认、默认直接域名映射」**。项目/工具专名一律泛化为「示例」，真实值入项目过程资产。
- **发布配置权威收敛到唯一过程资产 `deployment-config-guide.md`**（§六 重写为「过程资产与引用定义」）：原 `release/environments.yaml`/`policy.md`/`docs/ecs-deploy-design.md` 等引用（因 consult 已合并/归档）全部改为指向该过程资产；新增「过程资产必须记什么（①-⑦）+ 引用定义/次序 + 文档 vs 密钥库边界」。
- **交叉引用**：§八 #11↔`credential-management`（设计资产打码）与 `deployment-principles`（配置单一真相源+留痕）；§六 引用 `deployment-principles`（门禁10/11 环境/资源合规）、`credential-management`（机密取值）。
- **过程资产模板（CASE-019，同批落地）**：新增 `templates/deployment-config-guide.md.template`（①-⑦ 七小节 + 字段/占位 + "项目填什么"注释，无实例值）；§六 6.5 首次接入铺设。
- frontmatter：version 1.0.0→1.1.0-arb.1；lineage 加 `reclaim: from zy-ai-consult@2026-08-30 (CASE-014)`。

## 1.0.0-arb1（2026-08-23）

- 底座：`inbox/zy-ai-consult/release-management/SKILL.md`（e81304f0379e）。
- CASE-005 门禁并集：§二 发布门禁改写为两方并集 9 条通用门禁清单；依赖项目环境/脚本/测试套件的命令实例改写为「示例（项目侧适配）」格式（7 处），真实命令留在各项目 `release/` 目录；表前新增适配说明引言。
- 通用红线、四层级、重启策略、SemVer、回滚、迁移要求两侧逐字相同，直接保留 consult 文本。
- frontmatter 新增 lineage（zy-iot-ai / zy-ai-consult SHA256 前 12 位）+ `case: CASE-005`。
- 并集推导见 MERGE-NOTES.md 第二节。
