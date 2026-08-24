// 02 采集与分析 —— 单域 ER 数据文件
// 依据：{schema}.resources / {schema}.folders DDL + .naskb 描述仓库事实基线
// 域注册表：02-ingestion-analysis

window.ER_DATA = window.ER_DATA || {};
window.ER_DATA["02-ingestion-analysis"] = {
  "domain":      "02",
  "title":       "采集与分析",
  "slug":        "ingestion-analysis",
  "description": "知识资源（文件/目录）的元数据与描述：PG 主库 resources/folders 表 + 源端 .naskb 描述仓库（meta/index/folder/files/artifacts）双写。",

  "enums": [
    { "id": "ResourceStatus", "name": "资源状态", "description": "资源与知识库的对齐状态",
      "values": [
        { "code": "ok", "zh": "最新", "desc": "源与知识一致" },
        { "code": "stale_source", "zh": "源已更新", "desc": "源端变化待同步" },
        { "code": "stale_vector", "zh": "向量待更新", "desc": "描述已变但向量未同步" },
        { "code": "missing_source", "zh": "源已消失", "desc": "源端文件缺失，仅标记不删除" }
      ] },
    { "id": "HashAlgorithm", "name": "指纹算法", "description": "三级判定链使用的指纹粒度",
      "values": [
        { "code": "sha256:full", "zh": "全量指纹", "desc": "整文件 sha256" },
        { "code": "sha256:sample8x64k", "zh": "采样指纹", "desc": "8×64KB 采样（ADR-20260816-4），L2 复核用" }
      ] },
    { "id": "ProcessingPolicy", "name": "视频处理策略", "description": "视频分级处理策略",
      "values": [
        { "code": "metadata_only", "zh": "仅元数据", "desc": "影视类兜底" },
        { "code": "keyframes_only", "zh": "关键帧", "desc": "教学类" },
        { "code": "full", "zh": "全量", "desc": "个人录像类" }
      ] },
    { "id": "FileKind", "name": "资源类型", "description": "resources.kind",
      "values": [
        { "code": "file", "zh": "文件", "desc": "文件资源" },
        { "code": "folder", "zh": "目录", "desc": "目录资源（folder.json 描述）" }
      ] }
  ],

  "entities": [
    {
      "id": "resource",
      "name": "知识资源",
      "table": "{schema}.resources",
      "description": "文件级知识条目（PG 主库，v3 多来源：source_id + rel_path 唯一）",
      "fields": [
        {"name": "resource_id", "type": "UUID", "pk": true, "nn": true, "desc": "资源唯一标识（对外寻址锚点）"},
        {"name": "source_id", "type": "UUID", "pk": false, "nn": true, "fk": "source.source_id", "desc": "所属来源（跨域）"},
        {"name": "rel_path", "type": "text", "pk": false, "nn": true, "desc": "源内相对路径"},
        {"name": "parent_dir", "type": "text", "pk": false, "nn": false, "desc": "父目录"},
        {"name": "name", "type": "text", "pk": false, "nn": false, "desc": "文件名"},
        {"name": "kind", "type": "FileKind", "pk": false, "nn": true, "default": "file", "desc": "文件/目录"},
        {"name": "category", "type": "text", "pk": false, "nn": false, "desc": "AI 分类"},
        {"name": "tags", "type": "text[]", "pk": false, "nn": false, "desc": "AI 标签"},
        {"name": "summary", "type": "text", "pk": false, "nn": false, "desc": "AI 摘要（向量索引文本）"},
        {"name": "content_description", "type": "text", "pk": false, "nn": false, "desc": "内容描述（全文元数据）"},
        {"name": "file_type", "type": "text", "pk": false, "nn": false, "desc": "文件类型"},
        {"name": "file_hash", "type": "text", "pk": false, "nn": false, "desc": "指纹（ETag 来源）"},
        {"name": "hash_algorithm", "type": "HashAlgorithm", "pk": false, "nn": false, "desc": "指纹算法"},
        {"name": "size_bytes", "type": "bigint", "pk": false, "nn": false, "desc": "大小"},
        {"name": "mtime", "type": "datetime", "pk": false, "nn": false, "desc": "修改时间"},
        {"name": "ctime", "type": "datetime", "pk": false, "nn": false, "desc": "创建时间（L1 免检必要条件）"},
        {"name": "status", "type": "ResourceStatus", "pk": false, "nn": true, "default": "ok", "desc": "对齐状态"},
        {"name": "prev_hashes", "type": "text[]", "pk": false, "nn": false, "desc": "历史指纹（变更检测）"},
        {"name": "artifacts", "type": "jsonb", "pk": false, "nn": false, "desc": "MinerU 产物登记（artifacts 列表）"},
        {"name": "analyzed_at", "type": "datetime", "pk": false, "nn": false, "desc": "分析时间"},
        {"name": "created_at", "type": "datetime", "pk": false, "nn": true, "desc": "创建时间"},
        {"name": "updated_at", "type": "datetime", "pk": false, "nn": true, "desc": "更新时间"}
      ],
      "indexes": [
        {"fields": ["source_id", "rel_path"]},
        {"fields": ["parent_dir"]},
        {"fields": ["status"]},
        {"fields": ["hash_algorithm", "size_bytes", "file_hash"]}
      ]
    },
    {
      "id": "folder_entry",
      "name": "目录条目",
      "table": "{schema}.folders",
      "description": "目录级描述（ADR-20260818-1 决策 6：folder 独立表）",
      "fields": [
        {"name": "folder_id", "type": "UUID", "pk": true, "nn": true, "desc": "目录唯一标识"},
        {"name": "source_id", "type": "UUID", "pk": false, "nn": true, "fk": "source.source_id", "desc": "所属来源（跨域）"},
        {"name": "rel_path", "type": "text", "pk": false, "nn": true, "desc": "目录相对路径"},
        {"name": "parent_dir", "type": "text", "pk": false, "nn": false, "desc": "父目录"},
        {"name": "name", "type": "text", "pk": false, "nn": false, "desc": "目录名"},
        {"name": "summary", "type": "text", "pk": false, "nn": false, "desc": "目录描述"},
        {"name": "description", "type": "text", "pk": false, "nn": false, "desc": "目录描述（folder.json 同步）"},
        {"name": "tags", "type": "text[]", "pk": false, "nn": false, "desc": "标签"},
        {"name": "file_count", "type": "integer", "pk": false, "nn": false, "desc": "文件计数"},
        {"name": "updated_at", "type": "datetime", "pk": false, "nn": true, "desc": "更新时间"}
      ],
      "indexes": [ {"fields": ["source_id", "rel_path"]}, {"fields": ["parent_dir"]} ]
    },
    {
      "id": "naskb_index_entry",
      "name": ".naskb 索引条目",
      "table": ".naskb/index.json",
      "description": "源端轻量索引条目（index.json；files/ 下大字段为 FileDetail VO）",
      "fields": [
        {"name": "path", "type": "text", "pk": false, "nn": true, "desc": "相对 .naskb 所在目录的文件路径"},
        {"name": "file_hash", "type": "text", "pk": false, "nn": false, "desc": "指纹"},
        {"name": "hash_algorithm", "type": "HashAlgorithm", "pk": false, "nn": false, "desc": "指纹算法"},
        {"name": "summary", "type": "text", "pk": false, "nn": false, "desc": "摘要（轻量保留）"},
        {"name": "category", "type": "text", "pk": false, "nn": false, "desc": "分类"},
        {"name": "tags", "type": "text[]", "pk": false, "nn": false, "desc": "标签"},
        {"name": "analyzed_at", "type": "datetime", "pk": false, "nn": false, "desc": "分析时间"},
        {"name": "analyzer_version", "type": "text", "pk": false, "nn": false, "desc": "分析器版本"},
        {"name": "processing_policy", "type": "ProcessingPolicy", "pk": false, "nn": false, "desc": "视频处理策略"},
        {"name": "size_bytes", "type": "bigint", "pk": false, "nn": false, "desc": "大小"},
        {"name": "mtime", "type": "datetime", "pk": false, "nn": false, "desc": "修改时间"},
        {"name": "ctime", "type": "datetime", "pk": false, "nn": false, "desc": "创建时间"}
      ]
    }
  ],

  "value_objects": [
    {
      "id": "file_detail",
      "name": "文件详情（VO）",
      "type": "vo",
      "description": ".naskb/files/<rel>.json 大字段：全文/转写/OCR/EXIF 等原始分析数据",
      "fields": [
        {"name": "path", "type": "text", "pk": false, "nn": true, "desc": "相对路径"},
        {"name": "file_hash", "type": "text", "pk": false, "nn": true, "desc": "指纹"},
        {"name": "hash_algorithm", "type": "HashAlgorithm", "pk": false, "nn": false, "desc": "指纹算法"},
        {"name": "analyzed_at", "type": "datetime", "pk": false, "nn": false, "desc": "分析时间"},
        {"name": "analyzer_version", "type": "text", "pk": false, "nn": false, "desc": "分析器版本"},
        {"name": "analysis", "type": "json", "pk": false, "nn": false, "desc": "分类/摘要/标签/置信度"},
        {"name": "transcription", "type": "text", "pk": false, "nn": false, "desc": "音频转写"},
        {"name": "ocr_text", "type": "text", "pk": false, "nn": false, "desc": "OCR 全文"},
        {"name": "metadata", "type": "json", "pk": false, "nn": false, "desc": "EXIF/大小/类型等元数据"},
        {"name": "provenance", "type": "json", "pk": false, "nn": false, "desc": "来源标注（来源来源/模型/提示）"}
      ]
    },
    {
      "id": "doc",
      "name": "可检索描述文档（VO）",
      "type": "vo",
      "description": "检索/同步的输入载体（retrieval.py Doc）——文本仅摘要+描述，上下文含全文",
      "fields": [
        {"name": "path", "type": "text", "pk": false, "nn": true, "desc": "文档路径（相对/绝对语义差异见 design-code-gap）"},
        {"name": "kind", "type": "FileKind", "pk": false, "nn": true, "desc": "file|folder"},
        {"name": "text", "type": "text", "pk": false, "nn": false, "desc": "索引文本（仅摘要+描述——用户拍板）"},
        {"name": "summary", "type": "text", "pk": false, "nn": false, "desc": "摘要"},
        {"name": "category", "type": "text", "pk": false, "nn": false, "desc": "分类"},
        {"name": "tags", "type": "text[]", "pk": false, "nn": false, "desc": "标签"},
        {"name": "context", "type": "text", "pk": false, "nn": false, "desc": "RAG 上下文（含全文）"},
        {"name": "content_description", "type": "text", "pk": false, "nn": false, "desc": "内容描述"},
        {"name": "file_type", "type": "text", "pk": false, "nn": false, "desc": "文件类型"},
        {"name": "artifacts", "type": "json", "pk": false, "nn": false, "desc": "MinerU 产物登记"},
        {"name": "md_abs", "type": "text", "pk": false, "nn": false, "desc": "MinerU Markdown 绝对路径"},
        {"name": "file_hash", "type": "text", "pk": false, "nn": false, "desc": "指纹"},
        {"name": "hash_algo", "type": "HashAlgorithm", "pk": false, "nn": false, "desc": "指纹算法"},
        {"name": "source_id", "type": "UUID", "pk": false, "nn": false, "desc": "所属来源（staging 场景）"}
      ]
    },
    {
      "id": "artifact_record",
      "name": "MinerU 产物登记（VO）",
      "type": "vo",
      "description": "resources.artifacts jsonb 元素：解析产物（md/html/middle.json/images）",
      "fields": [
        {"name": "name", "type": "text", "pk": false, "nn": true, "desc": "产物名"},
        {"name": "relative_path", "type": "text", "pk": false, "nn": true, "desc": "相对路径"},
        {"name": "kind", "type": "text", "pk": false, "nn": true, "desc": "md|html|middle|images"},
        {"name": "source", "type": "text", "pk": false, "nn": false, "desc": "staging|persistent"}
      ]
    }
  ],

  "services": [
    { "id": "fs_adapter", "name": "文件系统适配",
      "description": "fs/base/local/webdav：来源访问抽象",
      "methods": [
        {"name": "create", "sig": "(protocol, url, auth) → adapter", "desc": "按协议创建适配器"},
        {"name": "scan", "sig": "(root) → entries[]", "desc": "目录枚举"},
        {"name": "stat", "sig": "(path) → {size, mtime, ctime}", "desc": "L1 免检取数"},
        {"name": "sample", "sig": "(path) → bytes[8×64k]", "desc": "L2 采样"},
        {"name": "stream", "sig": "(path, range) → stream", "desc": "下载代理读取"}
      ] },
    { "id": "desc_store", "name": ".naskb 仓库服务",
      "description": "描述仓库原语：set_entry/move_entry/remove_entry/check",
      "methods": [
        {"name": "set_entry", "sig": "(path, detail) → entry", "desc": "完整原数据+轻量索引双写（原子）"},
        {"name": "move_entry", "sig": "(from, to) → moved", "desc": "先移文件后迁条目"},
        {"name": "remove_entry", "sig": "(path) → removed", "desc": "删文件+原子写"},
        {"name": "check", "sig": "(entry) → valid|stale|missing", "desc": "对齐检查"}
      ] },
    { "id": "analysis_pipeline", "name": "分析管线",
      "description": "多模态分析编排（analyzer/document|image|audio|video|folder|mineru）",
      "methods": [
        {"name": "analyze_document", "sig": "(path) → Analysis", "desc": "PyMuPDF/MinerU + DeepSeek"},
        {"name": "analyze_image", "sig": "(path) → Analysis", "desc": "EXIF + MiMo"},
        {"name": "analyze_audio", "sig": "(path) → transcription", "desc": "ffmpeg 分段 + MiMo 转写"},
        {"name": "analyze_video", "sig": "(path) → VideoAnalysis", "desc": "分级策略"},
        {"name": "describe_folder", "sig": "(dir) → folder.json", "desc": "目录级描述"}
      ] }
  ],

  "relations": [
    {"from": "resource.source_id", "to": "source.source_id", "type": "N:1", "desc": "资源归属来源", "cross_domain": "01"},
    {"from": "folder_entry.source_id", "to": "source.source_id", "type": "N:1", "desc": "目录归属来源", "cross_domain": "01"}
  ]
};
