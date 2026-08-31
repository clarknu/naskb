---
name: credential-management
version: 1.7.0-arb.1
description: "项目机密与部署配置的**唯一去向**（credentialctl）。安全模型：AES-256-GCM 加密库（credential.json / credential.meta.json / config+token）整体提交进代码库；唯一留在库外的是 `init` **自动生成**的 master 密钥（换机/迁机凭它恢复；仓库含公开 salt/iter/keycheck → 它是唯一可离线爆破的靶子，须高熵）。master 密钥派生主密钥（PBKDF2-SHA256 600k）＋每机 DPAPI 自动解锁，迁机重输一次即重绑。**部署相关配置或密钥一律进库、用时从库取**；key 用 `{env}_{kind}` 命名（env=local/alpha/beta/release，kind 按凭据性质取名如 server/user/password/api_key，不强制 SSH）；按项目 scope 认证、越权拒绝、全程审计；数据在项目 `.credential`（仅 `.credential/unlock/` 的机器级 blob 不入库）。"
whenToUse: "接入新项目时（`init` **自动建库并生成一把 master 密钥**给你保存）+ 迁移既有明文凭据；但凡**配置/部署/调试线上环境或第三方服务需要 API key/访问令牌/口令/部署配置**时；生成配置/脚本/产物需引用凭据但不得写入真值、初始化或轮换某项目凭据区时。"
triggers:
  - "密钥管理"
  - "密钥库"
  - "访问凭据"
  - "访问令牌"
  - "API 密钥"
  - "API Key"
  - "敏感配置"
  - "加密配置"
  - "部署密钥"
  - "环境变量注入"
  - "凭据管理"
  - "credentials"
  - "access token"
  - "api key"
  - "credential"
  - "vault"
  - "secret"
lineage:
  origin: arb-hub
  case: CASE-013
  reclaim:
    from: zy-ai-consult
    at: "2026-08-30"
    note: 回收 consult `skills/credential-management` v1.7.0（项目侧领先版）；泛化为项目中性（去 zy-ai-consult 专名/实例，示例抽象化），供全部项目复用。
  note: 本枢纽受管技能（CASE-013 回收）。工具 credentialctl.ps1 与 skill 同捆在 `scripts/`；bundle 模式下 `.agents/skills/…` 一律按 `<本文件夹>/…` 解释，脚本路径 = `<本文件夹>/scripts/credentialctl.ps1`。v1.7.0-arb.1 采纳 consult 的模型反转（"加密库入库 + master 密钥外置"）与机密/非密拆分；示例已泛化。
---

# credential-management

本技能是项目**机密与部署配置的唯一去向**：但凡**部署相关配置或密钥，一律进本加密库、用时从库里取**（用 `<CREDENTIAL:proj/key>` 占位符引用）。它把散在各配置文件里的明文凭据收进项目内的加密库（`<项目根>\.credential`），**整个加密库连同获取凭据所需的 token 一起提交进代码库**；唯一**不放进代码库的是 master 密钥**（`init` 自动生成，给你保存，换机凭它恢复）。代码/仓库/日志/对话里只出现 `<CREDENTIAL:proj/key>` 占位符，真正需要值时（部署/注入）才经 `--env`/`--reveal` 解密。

它**驱动外置工具 `credentialctl.ps1`**（与技能同捆），并落实"占位符优先、加密库入库、按 scope 认证、全程审计"这条配置纪律。

> 层归属：L3 工具胶水（驱动 credentialctl 工具 + 贯彻部署/配置原则），作为常驻旁路（stage=bypass），流水线任意阶段可调用。

## 先读：设计模型（为什么这么设计）

**一句话：靠"加密库入库 + 一把上库外的主密钥"实现跨机恢复。** 这与 SOPS/age、git-crypt、ansible-vault 的模型一致。

- **进代码库（可提交）**：`credential.json`（AES-256-GCM 加密的条目）、`credential.meta.json`（salt/iter/keycheck）、`config`（scope token）。这些离开 master 密钥 **都解不出任何明文值**。
- **不进代码库**：**master 密钥**——由 `init` **自动生成**、打印一次给你保存；它是唯一的安全边界，也是唯一能跨机解锁的恢复钥匙。
- **跨机恢复流程**：clone 代码库（拿到加密库）→ 换机 → 输入 master 密钥 → `get --reveal`/`--env` 解出真值 → 该机自动绑定（写新 blob）。
- **⚠️ 推理**：因为 `salt`/`iter`/`keycheck` + 全部密文在仓库里公开，**整个库成了可离线爆破的目标**。破解者 clone 仓库→对每个猜测的 master 密钥跑 PBKDF2-SHA256 校验 keycheck（可秒验对错）。所以 master 密钥**必须高熵、随机、长**（`init` 已自动生成高熵值，不必手动设）；当前的 KDF 是 PBKDF2-SHA256 × 600k，对 GPU 离线并不重，**最强杠杆 = 主密熵**。若要更强抗离线，理想是 Argon2id（工具暂未实现，属后续升级点）。

## 数据文件与 gitignore 规则（不要搞错）

数据根（`Get-VaultRoot`）：`$env:credentialctl_HOME`，否则向上发现最近的 `.credential`，否则 `<cwd>\.credential`。

| 文件 | 内容 | 是否入库 |
|---|---|---|
| `credential.json` | 加密条目（AES-256-GCM，DEK 由主 KEK 包裹） | ✅ 提交 |
| `credential.meta.json` | salt / iter / keycheck | ✅ 提交 |
| `config` | 项目的明文 scope token（授权 list/get 用，非保密核心） | ✅ 提交 |
| `unlock\<machine>.bin` | 本机 DPAPI(CurrentUser, KEK) 解锁 blob——按机器生成、换机无用 | ❌ 只 gitignore 这个 |

**`.gitignore` 只需忽略 `.credential/unlock/`**（按机器生成的 blob，是每机优化项、非恢复数据；跨机恢复走 master 密钥，不靠它）：

```
.credential/unlock/
```

提交时只 `git add .gitignore .credential/config .credential/credential.json .credential/credential.meta.json`（**不要 `git add .credential` 全量**——那也会把 `config` 的 token、以及未来可能出现的机器 blob 一起带进来；用 `git add -n .credential` 先核对，确认没有 `unlock/` 下文件）。

> 注意：**不要**把整个 `.credential` 写进 gitignore（那会连恢复所需的加密库一起挡掉，跨机就废了）；只要忽略 `unlock/` 子目录。

## 命名约定（`{env}_{kind}`）

密钥/配置 key 统一用 **`{env}_{kind}`** 命名：**环境段在最前**（限定在哪个环境使用），`kind` 按凭据的**真实性质**取名（**不强制 SSH**）。

- **环境段**：`local`（本地研发）｜ `alpha`（线上研发＝部署文档的 dev）｜ `beta`（线上预发）｜ `release`（线上生产＝部署文档的 prod）。
- **kind 按性质取**（可加服务名前缀，如 `{service}_api_key`）：
  - 服务器地址/IP → `server`；端口 → `port`
  - 登录用户名 → `user`；密码 → `password`（网页登录用 `login_user` / `login_password`）
  - 确为 SSH 才用 `ssh_user` / `ssh_password`（一般服务器登录用 `user`/`password` 即可）
  - API 密钥 → `api_key`；令牌 → `token`；密钥 → `secret`
  - 数据库/缓存 → `db_url` / `db_password` / `redis_password`
- 例：线上主机（线上共用）→ `online_server`、`online_user`、`online_password`、`online_port`；本地研发机 → `local_server`、`local_port`、`local_user`、`local_password`。
- **共享/服务类**（跨环境或本库专用）可**不加环境段**，直接用描述名（如 `{service}_api_key`、`{service}_db_password`）；需要区分环境时再补环境段。

## 部署配置分类逻辑（环境作用域 × 资源类型）

> **部署配置逻辑**（完整见项目侧"部署配置文档"，部署配置单一真相源，每次部署先读；该过程资产由 `release-management` 定义）：**密钥库只放「机密」**（口令 / API Key / 令牌 / 密钥材料 / 访问密钥 Secret）；**非密部署配置**（IP、域名、地址、本地路径、端口、用户名、库名、URL、模型名）放在**部署配置文档**，**不进密钥库**。部署文档同时记录**「部署步骤 → 需要的密钥库 Key」**对照表，**用到哪个 Key 才去密钥库取**（绝不提前/批量泄露）。

1. **环境作用域**：`共享`（环境中性，不加前缀）｜ `环境作用域`（随环境不同，加 `{env}_` 前缀）。
2. **资源/组件类型**（kind）：按机密真实性质取名，不限定 SSH。

**关键规则：只有机密进密钥库；非密配置进部署文档；「共享」不加前缀、「随环境不同」加 `{env}_`。**

**进密钥库的机密**（示例，模式化）：
- 环境中性：`{service}_api_key`、`{provider}_access_key_secret`（配 `{provider}_access_key_id`，二者成对）、`{service}_db_password`、`redis_password`、`online_password`、`{service}_*`（密钥/令牌/口令）。
- 环境作用域：`{env}_password`、`{env}_db_password`、`{env}_{service}_api_key`（每 App 独立 Key 时）。

**进部署配置文档的非密配置**：`{service}_host`/`{service}_port`/`{service}_user`、`{env}_db_name`/`{env}_db_user`、`redis_host`/`redis_port`、`online_server`/`online_user`/`online_port`、`{env}_server`/`{env}_user`/`{env}_port`、`{service}_base_url`、`{env}_{service}_project`/`{env}_{service}_app_id`/`{env}_{service}_workflow_id`、各域名/地址/路径/URL。
- **开发 Key 与 运行 Key 分离**：`{service}_api_key` 等记的是**项目研发/测试/演示（自主运行）**用 Key；**AI Coding（开发/编码）**用的 Key 是另一把，**不进项目密钥库**（由编码 Agent/平台各自持有），严禁混用。

## 触发条件

- **部署需要机密时**（写任何 deployment 脚本/清单、需要线上环境密钥或第三方令牌口令）——**机密才进本库、用时从库取**；**非密部署配置进部署配置文档**。绝不把明文机密写进脚本/仓库。
- **⛔ 设计资产副本同样必须打码**——凡"我们开发并对外部署"的设计资产（**工作流/子流 DSL、模型提供方/插件配置、MCP 服务器、自建协议转换/代理层、部署拓扑**），其**代码库副本**里 key/令牌一律只存 **`<CREDENTIAL:proj/key>` 引用**，真值进本库；导入/运行时才从库注入真值。若 DSL/配置/脚本此前硬编码了明文密钥（如 `sk-…`、`app-…`），迁移进库**必须打码**（此为「落库铁律」的密钥侧约束，见 `release-management` §八 #11）。
- **新建项目**接入密钥区（`init` 自动建库并生成 master 密钥）、迁移既有明文凭据、初始化/轮换某项目凭据区。
- 需要**线上部署环境的密钥**、**第三方服务的访问令牌/API key/口令**、或要往线上 environment 注入某个值。
- 生成配置/脚本/部署清单时，需要引用某个凭据但**不能把真值写进去**。
- 需要知道某项目**允许读哪些凭据**（scope），或要**初始化/轮换**某项目的凭据区。

## 工具定位（优先级）

```
1. $env:CREDENTIALCTL_SCRIPT   —— 若设置，即为 CLI 路径
2. <本技能目录>\scripts\credentialctl.ps1   —— 与 skill 同捆，随 bundle/项目走
```

始终**以脚本文件方式调用**（`pwsh -NoProfile -File <cli> …`），**切勿**把其加密代码内联进 `pwsh -Command`（Windows Defender AMSI 会对加密原语触发启发式误报）。需要非交互（CI/agent）时用环境变量传主密码：`$env:credentialctl_PASSPHRASE`。

## 接入新项目：完整清单（skill 自己完成，不手抄）

> 以下每步都能独立跑通；`<cli>` = 上面定位到的脚本路径，`<proj>` = 项目 slug。

```powershell
$env:credentialctl_HOME = "<项目根>\.credential"        # 显式指定库根（也可省略，默认向上发现/当前目录）

# 1) 建库：自动生成 master 密钥（唯一恢复钥匙）+ 绑定本机
pwsh -NoProfile -File <cli> init
#    init 会**自动生成一把高熵 master 密钥并打印一次**——立刻保存到你的密码管理器（换机/迁机唯一恢复钥匙）。
#    非交互/CI 可用 $env:credentialctl_PASSPHRASE 提供主密（此时不打印密钥）。

# 2) 登记项目 + 生成 scope token（自动写入 .credential\config）
pwsh -NoProfile -File <cli> project init <proj> --scope "DATABASE_URL,local_*,alpha_*,beta_*,release_*,*_KEY,*_SECRET,*_TOKEN,*_API_KEY,*_PASSWORD,*_DB_PW,*_PW" --config "<项目根>\.credential\config"

# 3) （推荐）迁移既有明文凭据：每个密钥走 --file，值绝不出现在 argv/输出
#    从 .env / *_prod_secrets.env 逐一取出 → 写临时文件 → add --secret --file <临时> → 删除临时
#    典型 scope 族（据此补齐 scope，避免像 REDIS_PW 那样漏 *_PW）：
#      local_*  alpha_*  beta_*  release_*  *_KEY  *_SECRET  *_TOKEN  *_API_KEY  *_PASSWORD  *_PASS  *_PW  *_DB_PW  DATABASE_URL

# 4) gitignore：只忽略机器级 blob
#    写进 .gitignore：.credential/unlock/

# 5) 提交（只提交加密库 + gitignore，别带机器 blob / 无关改动）
git add .gitignore .credential/config .credential/credential.json .credential/credential.meta.json
git commit -m "chore(credential): 接入本地加密密钥库（master 密钥不入库）"

# 6) 验证
pwsh -NoProfile -File <cli> list <proj>                     # 列出 scope 内 key 名
pwsh -NoProfile -File <cli> get <proj> <KEY>                # 占位符 <CREDENTIAL:…>
pwsh -NoProfile -File <cli> get <proj> <KEY> --env <NAME>   # 注入真实环境变量（审计）
```

此后 `get`/`list` 会自动从 `.credential\config` / `$env:credentialctl_TOKEN` 解析 token，无需传 `-t`。

## 密钥写入（关键：值怎么进，才不会泄露）

**规则优先级：`--file`（临时文件）> OS 级 stdin 重定向 > `--value`（会进 argv，禁止用于真实密钥）。**

- ✅ `--file <path>`：把值写进一个临时/已 gitignore 文件（用后删除），命令里不出现值。
- ✅ OS 级 stdin 重定向：`Get-Content secret.txt | pwsh -NoProfile -File <cli> add <proj> <key> --secret`。注意**必须是新开 pwsh 进程的 stdio 重定向**，`$v | & <cli> add …`（PowerShell 对象管道喂给脚本本身）**不生效**——脚本没有绑定管道参数，会报 `cannot bind pipeline input`。
- ❌ 禁止 `--value <v>` 传真实密钥（脚本会警告"值落 argv"）。
- 非敏感配置用 `add <proj> <key> --config --plain --file <path>`（明文存储；非保密项，与密钥**同源统一从本库取**，不散落 `.env`）。

写入后可用 `get <proj> <key> --reveal`（或 `--env`）验证，但**对比用内存变量、只打印 MAC，不要打印真值**。

## 读取 / 注入（常见路径）

1. **列出该项目可读凭据**（不含值）：`<cli> list <proj>`
2. **取占位符**（安全嵌入配置/脚本/产物）：`<cli> get <proj> <key>` → `<CREDENTIAL:proj/key>`
3. **注入线上环境变量**（发出 `$env:NAME='…'`）：`<cli> get <proj> <key> --env NAME`
4. **取真值**（仅部署/测试）：`<cli> get <proj> <key> --reveal`

在新机器上，第一次需要真值的 `get` 会提示输入 master 密钥一次（本机随即重绑）；`list` 与占位符读取无需解锁。

## 主密钥与跨机（务必记住）

- 主密钥 = `init` **自动生成**的 master 密钥（高熵、打印一次）；`KEK = PBKDF2-HMAC-SHA256(master, salt, 600k)`，**永不明文落盘**。
- **同机同用户**：`unlock\<机器>.bin` 用 DPAPI(CurrentUser, KEK) 自动解锁，无需输入。
- **迁到新机**：**只有 master 密钥能解锁**，重输一次 → 写该机自己的 blob → 之后自动解锁。
- `machine bind`（绑定本机）· `machine unbind`（解除本机）· `machine list`。
- **⚠️ master 密钥是唯一钥匙**：`init` 打印的这把 master 密钥**就是恢复钥匙**（已接通、可真正解锁，不是占位）。把它存进你自己的密码管理器；master 密钥与所有机器 blob 都丢 → 设计上不可恢复。

## scope 设计（用什么模式，漏了什么会坑）

scope 控制该项目 scope token 能 `list`/`get` 哪些 key。它是一个**模式列表**（支持 `*` 通配，`In-Scope` 用 `-like` 匹配）。

- **用"族通配"而非逐条硬编**：像 `*_KEY,*_SECRET,*_TOKEN,*_API_KEY,*_PASSWORD,*_PASS,*_PW,*_DB_PW`，覆盖常见密钥后缀。**注意**：`*_DB_PW` 不涵盖 `REDIS_PW` 这种裸 `_PW` 结尾的 key，需要额外的 `*_PW`（这是接入时实际踩到的坑）。
- **环境段通配**：按 `{env}_{kind}` 命名，scope 里加 `local_*,alpha_*,beta_*,release_*,online_*`（`online_*` = 线上共用主机/资源）覆盖各环境；不区分环境的共享/服务类凭据用类型通配（`*_KEY` 等）。
- 常用集合示例：`DATABASE_URL,local_*,alpha_*,beta_*,release_*,*_KEY,*_SECRET,*_TOKEN,*_API_KEY,*_PASSWORD,*_PASS,*_PW,*_DB_PW`。
- **scope 目前只能在 `project init` / `project add` 时设置**；现有项目**没有改 scope 的 CLI 命令**。要追加 scope，目前需编辑 `credential.json` 里 `projects.<proj>.scope` 数组（或重建项目）。若需常态增删，建议给工具加 `project scope <proj> <patterns…>` 命令（见"已知边界-待补"）。
- scope 只做授权（list/get），不参与加解密；越权 key 一律拒绝并记审计。

## 输出格式

| 命令 | 输出 |
|---|---|
| `<cli> list <proj>` | 所有 key 名（scope 内，无值）。注意脚本把结果**以单个换行拼接的字符串**输出 |
| `<cli> get <proj> <key>` | `<CREDENTIAL:proj/key>` 占位符 |
| `<cli> get <proj> <key> --env NAME` | `$env:NAME='<值>'`（单引号内 `'` 转义为 `''`） |
| `<cli> get <proj> <key> --reveal` | 真值（仅部署/测试用，审计记录 reveal=True） |

## 硬规则

1. **仅机密进库（铁律）**：密钥/令牌/口令/密钥材料等**机密**才进本库；**非密部署配置**（IP、域名、地址、端口、用户名、库名、URL、路径、模型名）在**部署配置文档**，**不进密钥库**。生成配置/清单/脚本时，机密一律用 `<CREDENTIAL:proj/key>` 占位符、仅部署注入那步取真值；非密配置直接写进部署文档/脚本（非密、无需占位）。
2. **环境作用域分类**：机密里「共享」不加前缀（`{provider}_api_key`/`{service}_db_password`/`redis_password`…）、「随环境不同」加 `{env}_`（`{env}_password`/`{env}_db_password`…）；非密配置的分段命名同规则、但**放部署文档**。完整结构见项目侧部署配置文档。
3. **明文真值绝不进仓库/日志/错误信息/对话**；**加密库整体可入库**（这是模型的核心，别把库也用 gitignore 挡掉）。
4. **不读 scope 外 key**（被拒即表示不属于该项目，勿绕过）；`--env`/`--reveal` 是审计过的 reveal 动作，仅为真实部署/验证需要而用。
5. **非密配置不进库**：部署类非密配置（IP/域名/地址/端口/用户名/库名/URL/路径）记录在**部署配置文档**，**不以 `--config --plain` 进库**；库内只存 `--secret` 机密。部署文档同时维护**「部署步骤 → 密钥库 Key」**对照表，用到某 Key 才取。
6. token 只授权 list/get（scope 内），不参与加解密；随 `config` 进库、但解不出任何值——保密核心是 master 密钥。
7. **值写入不落 argv**：用 `--file` / OS 级 stdin；`--value` 仅限测试且会警告。
8. **SSH 私钥入密钥库、内存加载**：SSH 私钥是机密，**入密钥库**（如 `online_ssh_key`），需要时 `get --reveal` 取回**内存**加载（如 `paramiko .from_private_key(io.StringIO(pem))`），**不落明文盘、不进仓库**；明文 `.pem` 文件仅作临时/降级载体，禁止作为常规存放。

## 已知边界 / 局限（使用前知悉）

- **Windows 专用**：依赖 DPAPI + AesGcm；跨平台（age/SOPS）未实现，仅预留抽象。脚本须以文件方式调用（AMSI）。
- **改 scope 无 CLI**：现有项目只能编辑 `credential.json` 的 scope（或重建）；建议后续补 `project scope` 命令。
- **`project init` 会把 token 打到 stdout**：换机/受信终端执行，别在会进日志的上下文里跑；介意可 `project token <proj>` 轮换（仍回显）。
- **KDF 是 PBKDF2-SHA256 × 600k**：对 GPU 离线爆破不算重；更强的抗离线需 Argon2id（未实现）或高熵 master 密钥。
- **值写入的管道陷阱**：PowerShell 对象管道喂不进脚本（无管道参数）；要用 `--file` 或 OS 级 stdio 重定向。

## 变更（管理员，人类或受信操作者）

`<cli> add <proj> <key> --secret --file <path>`（值经临时/已 gitignore 文件传入，避免落 argv）。非敏感：`add <proj> <key> --config --plain --file <path>`。轮换项目 token：`project token <proj>`。审计：`<cli> audit`。查看/移位机器绑定：`machine bind|unbind|list`。

## Windows 注意

脚本方式调用；不推荐加整机/整目录 Defender 排除（文件调用即可，且避免密钥进 argv）。
