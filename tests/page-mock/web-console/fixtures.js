/* tests/page-mock/web-console/fixtures.js
 * Page Mock 测试共享的「契约形状」mock 数据。
 * 形状取自 design/04-platform-api/data/rest/*（GET /api/kb/search、/api/sources、
 * /api/jobs、/api/files/{rid}、(preview) 的成功响应示例）。
 */

/* GET /api/kb/search —— 3 条命中（TC-M001） */
export const searchHits = [
  { resource_id: 'r1', path: 'docs/合同.pdf', score: 0.83, summary: '月租金为 3,200 元。',
    category: '合同', tags: ['租赁'], stale: false, nas: 'home-nas', source_alias: 'home-nas-docs' },
  { resource_id: 'r2', path: 'docs/补充协议.pdf', score: 0.72, summary: '押金与租期约定。',
    category: '协议', tags: ['押金'], stale: true, nas: '', source_alias: 'home-nas-docs' },
  { resource_id: 'r3', path: 'notes/出行证件.md', score: 0.61, summary: '身份证/护照清单。',
    category: '', tags: ['证件'], stale: false, nas: 'backup', source_alias: 'backup-nas' },
];

/* GET /api/sources —— 来源列表（契约：stats 聚合 + last_scan_at） */
export const sourcesList = [
  { source_id: 's1', alias: 'home-nas-docs', protocol: 'local', access_mode: 'ro',
    root_path: 'D:\\NAS\\docs', deep: false, enabled: true,
    stats: { files: 120, ok: 118, stale_source: 1, missing_source: 1, analyzed: 105, chunks: 0 },
    last_scan_at: '2026-08-24T10:00:00' },
];

/* GET /api/jobs —— 任务列表（契约：kind/status/progress/result/error/created_at） */
export const jobsList = [
  { id: '0a1b2c3d4e5f', kind: 'scan', status: 'running', progress: 0.4, message: '处理中…',
    result: null, error: '', created_at: '2026-08-24T10:05:00' },
  { id: '1b2c3d4e5f6a', kind: 'analyze', status: 'completed', progress: 1, message: '',
    result: { added: 2, stale_source: 0, missing: 0, deep: { chunks: 12 } }, error: '',
    created_at: '2026-08-23T09:00:00' },
];

/* GET /api/files/{rid} —— 文件元数据（契约：resource + download_url） */
export const fileMeta = (rid = 'r1') => ({
  resource: {
    name: '合同.pdf',
    rel_path: 'docs/合同.pdf',
    category: '合同',
    tags: ['租赁', '2026'],
    summary: '月租金为 3,200 元。',
    content_description: '房屋租赁合同（押一付三）。',
    file_hash: 'sha256:abc123def456',
    hash_algorithm: 'sha256',
    size_bytes: 120,
    mtime: '2026-08-01T10:00:00',
    analyzed_at: '2026-08-02T10:00:00',
    status: 'ok',
  },
  download_url: '/api/files/' + rid + '/download?src=s1',
});

/* GET /api/files/{rid}/preview —— 按 viewable 分派（契约：viewable + url/content/parsed_url/reason） */
export const filePreview = (viewable, extra = {}) => Object.assign({ viewable }, extra);
