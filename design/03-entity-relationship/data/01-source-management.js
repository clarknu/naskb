// 01 来源管理 —— 单域 ER 数据文件
// 依据：public.sources / public.nas_registry DDL 事实基线（project-code-domain 报告）
// 域注册表：01-source-management

window.ER_DATA = window.ER_DATA || {};
window.ER_DATA["01-source-management"] = {
  "domain":      "01",
  "title":       "来源管理",
  "slug":        "source-management",
  "description": "知识来源注册与安全边界：来源即资源寻址的根（resource_id = source_id + rel_path），ro|rw 访问模式，NAS 五要素身份注册。",

  "enums": [
    { "id": "AccessMode", "name": "访问模式", "description": "来源是否允许系统写源端",
      "values": [
        { "code": "ro", "zh": "只读知识库", "desc": "源端一个字节不写；停源/缺源后检索仍可用（带徽章）" },
        { "code": "rw", "zh": "可写", "desc": "保留源端 .naskb 双写；唯一可整理重组的来源类型" }
      ] },
    { "id": "SourceProtocol", "name": "来源协议", "description": "支持的来源接入协议",
      "values": [
        { "code": "local", "zh": "本机目录", "desc": "本机目录/NFS/iSCSI 挂载点" },
        { "code": "webdav", "zh": "WebDAV", "desc": "远程 NAS WebDAV 端点" }
      ] }
  ],

  "entities": [
    {
      "id": "source",
      "name": "知识来源",
      "table": "public.sources",
      "description": "来源注册表：每个来源一个资源根（安全边界）",
      "fields": [
        {"name": "source_id", "type": "UUID", "pk": true, "nn": true, "desc": "来源唯一标识"},
        {"name": "alias", "type": "varchar(64)", "pk": false, "nn": true, "uq": true, "desc": "来源别名"},
        {"name": "protocol", "type": "SourceProtocol", "pk": false, "nn": true, "default": "local", "desc": "接入协议"},
        {"name": "access_mode", "type": "AccessMode", "pk": false, "nn": true, "default": "ro", "desc": "ro/rw 访问模式"},
        {"name": "root_path", "type": "varchar(1024)", "pk": false, "nn": false, "desc": "local：本机根路径（挂载盘/网络挂载）"},
        {"name": "url", "type": "varchar(1024)", "pk": false, "nn": false, "desc": "webdav：远程 URL"},
        {"name": "username", "type": "varchar(128)", "pk": false, "nn": false, "desc": "webdav 账号（不出 API）"},
        {"name": "password", "type": "text", "pk": false, "nn": false, "desc": "webdav 密码（加密存储策略待定，见 design-code-gap）"},
        {"name": "verify_ssl", "type": "boolean", "pk": false, "nn": true, "default": "true", "desc": "webdav SSL 校验（群晖自签默认 false）"},
        {"name": "host", "type": "varchar(255)", "pk": false, "nn": false, "desc": "继承自 nas_registry（五要素一中继）"},
        {"name": "port", "type": "integer", "pk": false, "nn": false, "desc": "继承自 nas_registry"},
        {"name": "nas_id", "type": "UUID", "pk": false, "nn": false, "fk": "nas_reg.nas_id", "desc": "关联 NAS 五要素身份"},
        {"name": "schema_name", "type": "varchar(128)", "pk": false, "nn": false, "desc": "PG 独立 schema（nas_<proto>_<host>_<port>_u<h12>）"},
        {"name": "label", "type": "varchar(255)", "pk": false, "nn": false, "desc": "备注"},
        {"name": "scan_auto", "type": "boolean", "pk": false, "nn": true, "default": "false", "desc": "自动扫描开关"},
        {"name": "scan_interval_min", "type": "integer", "pk": false, "nn": true, "default": "60", "desc": "自动扫描间隔（分钟，下限 5）"},
        {"name": "deep", "type": "boolean", "pk": false, "nn": true, "default": "false", "desc": "深度分析开关（REQ-R5-06 系统级）"},
        {"name": "enabled", "type": "boolean", "pk": false, "nn": true, "default": "true", "desc": "启用/停用"},
        {"name": "last_scan_at", "type": "datetime", "pk": false, "nn": false, "desc": "最近扫描时间"},
        {"name": "created_at", "type": "datetime", "pk": false, "nn": true, "desc": "创建时间"},
        {"name": "updated_at", "type": "datetime", "pk": false, "nn": true, "desc": "更新时间"}
      ],
      "indexes": [ {"fields": ["alias"]} ]
    },
    {
      "id": "nas_reg",
      "name": "NAS 五要素身份",
      "table": "public.nas_registry",
      "description": "PG 多 NAS 向量库的身份注册（REQ-R4）：协议+主机+端口+账号（sha1 前 12 位入 schema 名）",
      "fields": [
        {"name": "nas_id", "type": "UUID", "pk": true, "nn": true, "desc": "NAS 身份唯一标识"},
        {"name": "proto", "type": "varchar(16)", "pk": false, "nn": true, "desc": "协议（当前 webdav/local 语义）"},
        {"name": "host", "type": "varchar(255)", "pk": false, "nn": true, "desc": "主机"},
        {"name": "port", "type": "integer", "pk": false, "nn": true, "desc": "端口"},
        {"name": "user_hash", "type": "varchar(16)", "pk": false, "nn": true, "desc": "账号 sha1 前 12 位"},
        {"name": "schema_name", "type": "varchar(128)", "pk": false, "nn": true, "uq": true, "desc": "nas_<proto>_<host>_<port>_u<h12>"},
        {"name": "created_at", "type": "datetime", "pk": false, "nn": true, "desc": "创建时间"}
      ]
    }
  ],

  "value_objects": [
    {
      "id": "source_stats",
      "name": "来源一致性统计（VO）",
      "type": "vo",
      "description": "一致性报告 knowledge 载荷：PgStore.source_stats 聚合派生（count/filter），非持久表；PG 不可达时含 error（不静默）——P-004 对齐（2026-08-24 用户拍板：设计与实现一致化）",
      "fields": [
        {"name": "files", "type": "integer", "pk": false, "nn": false, "desc": "资源总数"},
        {"name": "ok", "type": "integer", "pk": false, "nn": false, "desc": "status=ok 数"},
        {"name": "stale_source", "type": "integer", "pk": false, "nn": false, "desc": "源已更新数"},
        {"name": "missing_source", "type": "integer", "pk": false, "nn": false, "desc": "源已消失数"},
        {"name": "analyzed", "type": "integer", "pk": false, "nn": false, "desc": "已分析数（summary 非空）"},
        {"name": "chunks", "type": "integer", "pk": false, "nn": false, "desc": "条款级 chunk 行数（level='chunk'）"},
        {"name": "error", "type": "text", "pk": false, "nn": false, "desc": "PG 不可达时内嵌错误（不静默，DD-009 报告端点语义）"}
      ]
    }
  ],
  "services": [
    { "id": "source_service", "name": "来源服务",
      "description": "来源注册/测试/启停/删除/变更确认的领域服务（server/routes_sources.py）",
      "methods": [
        {"name": "register", "sig": "(SourceIn, test=true) → Source", "desc": "连通测试通过后注册"},
        {"name": "test_connectivity", "sig": "(source_id) → {ok, ms, error}", "desc": "连通性测试"},
        {"name": "list_changes", "sig": "(source_id) → {added[], changed[], missing[]}", "desc": "扫描差异清单"},
        {"name": "confirm_and_analyze", "sig": "(source_id, rel_paths[]) → job_id", "desc": "勾选确认 → 对账 + AI 分析"}
      ] }
  ],

  "relations": [
    {"from": "source.nas_id", "to": "nas_reg.nas_id", "type": "N:1", "desc": "来源归属 NAS 五要素身份（仅多 NAS 场景）"}
  ]
};
