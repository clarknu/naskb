/* NASKB 知识库系统 v0.1 —— Web UI（Vue3 全局构建，无打包步骤） */
/* global Vue */
const { createApp, reactive, ref, computed, onMounted, watch } = Vue;

/* ────────────────────────── API 客户端 ────────────────────────── */
const state = reactive({
  route: location.hash.replace(/^#\/?/, "") || "search",
  token: localStorage.getItem("naskb_token") || "",
  authRequired: false,
  anonymousRead: true,
  toast: "",
});

let toastTimer = null;
function toast(msg) {
  state.toast = msg;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { state.toast = ""; }, 2600);
}

async function api(path, opts = {}) {
  const headers = Object.assign({}, opts.headers || {});
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  if (opts.body && typeof opts.body !== "string") {
    opts = Object.assign({}, opts, { body: JSON.stringify(opts.body) });
    headers["Content-Type"] = "application/json";
  }
  const r = await fetch(path, Object.assign({}, opts, { headers }));
  if (r.status === 401) {
    const err = new Error("需要管理员令牌（右上角设置）");
    err.code = 401;
    throw err;
  }
  let data = null;
  try { data = await r.json(); } catch (e) { /* 空响应 */ }
  if (!r.ok) {
    const detail = data && (data.detail || data.error);
    const err = new Error(typeof detail === "object"
      ? JSON.stringify(detail) : (detail || ("HTTP " + r.status)));
    err.status = r.status;
    err.data = data;
    throw err;
  }
  return data;
}

function fmtSize(n) {
  n = Number(n || 0);
  if (n < 1024) return n + " B";
  const units = ["KB", "MB", "GB", "TB"];
  let i = -1;
  do { n /= 1024; i++; } while (n >= 1024 && i < units.length - 1);
  return n.toFixed(n >= 100 ? 0 : 1) + " " + units[i];
}
function fmtTime(s) {
  if (!s) return "—";
  try {
    const d = new Date(s);
    return isNaN(d) ? s : d.toLocaleString("zh-CN", { hour12: false });
  } catch (e) { return s; }
}
function statusBadge(st) {
  if (!st || st === "ok") return ["ok", "最新"];
  if (st === "stale_source") return ["warn", "源已更新"];
  if (st === "stale_vector") return ["warn", "向量待更新"];
  if (st === "missing_source") return ["bad", "源已消失"];
  return ["", st];
}

/* ────────────────────────── 检索 / 问答 ────────────────────────── */
const SearchView = {
  setup() {
    const q = ref(""), hits = ref([]), engine = ref(""), searching = ref(false);
    const question = ref(""), answer = ref(null), asking = ref(false);
    const searchErr = ref(""), askErr = ref("");
    async function doSearch() {
      const query = q.value.trim();
      if (!query) return;
      searching.value = true; searchErr.value = "";
      try {
        const d = await api("/api/kb/search?query=" +
          encodeURIComponent(query) + "&top_k=20");
        engine.value = d.engine; hits.value = d.hits || [];
        if (d.hint) toast(d.hint);
      } catch (e) { searchErr.value = e.message; }
      searching.value = false;
    }
    async function doAsk() {
      const text = question.value.trim();
      if (!text) return;
      asking.value = true; askErr.value = ""; answer.value = null;
      try {
        answer.value = await api("/api/ask", {
          method: "POST",
          body: { question: text, top_k: 5 },
        });
      } catch (e) { askErr.value = e.message; }
      asking.value = false;
    }
    function openFile(h) {
      if (!h.resource_id) { toast("该结果无资源定位（PG 未启用）"); return; }
      window.dispatchEvent(new CustomEvent("open-file", {
        detail: { rid: h.resource_id, src: h.nas || h.source_alias || "" },
      }));
    }
    return { q, hits, engine, searching, searchErr, doSearch,
             question, answer, asking, askErr, doAsk, openFile,
             fmtSize };
  },
  template: `
  <div>
    <div class="card">
      <h2>🔍 检索 <span class="badge" :class="engine==='pg'?'accent':''">{{ engine }}</span></h2>
      <div class="row">
        <input type="text" v-model="q" style="flex:1" placeholder="关键词或语义描述（如：出行要带的证件）" @keydown.enter="doSearch">
        <button @click="doSearch" :disabled="searching">{{ searching ? '检索中…' : '检索' }}</button>
      </div>
      <div class="error" v-if="searchErr">{{ searchErr }}</div>
      <div style="margin-top:12px">
        <table v-if="hits.length">
          <tbody>
            <tr v-for="(h,i) in hits" :key="i" class="clickable" @click="openFile(h)">
              <td>
                <div class="path">{{ i+1 }}. {{ h.path }}</div>
                <div class="row sub" style="margin-top:3px">
                  <span class="badge">分数 {{ Number(h.score).toFixed(3) }}</span>
                  <span class="badge" v-if="h.category">{{ h.category }}</span>
                  <span class="badge warn" v-if="h.stale">⚠️ 过期</span>
                  <span class="badge" v-for="t in (h.tags||[]).slice(0,6)" :key="t">{{ t }}</span>
                  <span class="badge accent" v-if="h.nas">{{ h.nas }}</span>
                </div>
                <div class="summary" v-if="h.summary">{{ h.summary }}</div>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="hint" v-else-if="!searching">输入关键词开始检索；支持语义向量与关键词自动降级。</div>
      </div>
    </div>

    <div class="card">
      <h2>💬 问答</h2>
      <div class="row">
        <input type="text" v-model="question" style="flex:1" placeholder="向知识库提问（如：月租金是多少？和谁签的？）" @keydown.enter="doAsk">
        <button @click="doAsk" :disabled="asking">{{ asking ? '生成中…' : '提问' }}</button>
      </div>
      <div class="error" v-if="askErr">{{ askErr }}</div>
      <div style="margin-top:12px" v-if="answer">
        <div class="answer">{{ answer.answer }}</div>
        <div class="hint" v-if="answer.sources && answer.sources.length">
          来源：<div v-for="s in answer.sources" :key="s">· {{ s }}</div>
        </div>
      </div>
    </div>
  </div>`,
};

/* ────────────────────────── 浏览 ────────────────────────── */
const BrowseView = {
  setup() {
    const sources = ref([]), cur = ref(""), dir = ref("");
    const dirs = ref([]), files = ref([]), loading = ref(false);
    const err = ref("");

    async function loadSources() {
      const d = await api("/api/sources");
      sources.value = d.sources || [];
      if (!cur.value && sources.value.length) {
        cur.value = sources.value[0].source_id;
        await loadTree();
      }
    }
    async function loadTree() {
      if (!cur.value) return;
      loading.value = true; err.value = "";
      try {
        const d = await api("/api/tree?src=" + encodeURIComponent(cur.value) +
          "&dir=" + encodeURIComponent(dir.value));
        dirs.value = d.dirs || []; files.value = d.files || [];
      } catch (e) { err.value = e.message; dirs.value = []; files.value = []; }
      loading.value = false;
    }
    function enter(d) { dir.value = d.rel_path; loadTree(); }
    function up() {
      if (!dir.value) return;
      const p = dir.value.split("/");
      p.pop();
      dir.value = p.join("/");
      loadTree();
    }
    const crumbs = computed(() => {
      const parts = dir.value ? dir.value.split("/") : [];
      const out = [{ name: "根", rel: "" }];
      let acc = "";
      for (const p of parts) { acc = acc ? acc + "/" + p : p; out.push({ name: p, rel: acc }); }
      return out;
    });
    function open(f) {
      window.dispatchEvent(new CustomEvent("open-file", {
        detail: { rid: f.resource_id, src: cur.value },
      }));
    }
    function thumbable(name) {
      return /\.(jpe?g|png|gif|webp|bmp|mp4|mkv|mov|webm|avi)$/i.test(name);
    }
    onMounted(loadSources);
    return { sources, cur, dir, dirs, files, loading, err, loadTree,
             enter, up, crumbs, open, thumbable, fmtSize, statusBadge };
  },
  template: `
  <div class="card">
    <h2>📁 浏览知识库
      <select v-model="cur" @change="dir='';loadTree()" style="max-width:280px">
        <option v-for="s in sources" :key="s.source_id" :value="s.source_id">{{ s.alias }}（{{ s.access_mode.toUpperCase() }}）</option>
      </select>
      <button class="ghost small" @click="loadTree">刷新</button>
    </h2>
    <div class="breadcrumb" style="margin-bottom:10px">
      <span v-for="(c,i) in crumbs" :key="c.rel">
        <span class="crumblink" @click="dir=c.rel;loadTree()">{{ c.name }}</span><span v-if="i<crumbs.length-1"> / </span>
      </span>
    </div>
    <div class="error" v-if="err">{{ err }}</div>
    <div class="hint" v-if="loading">加载中…</div>
    <table v-else-if="dirs.length || files.length">
      <thead><tr><th style="width:46%">名称</th><th>大小</th><th>状态</th><th>摘要</th></tr></thead>
      <tbody>
        <tr v-if="dir" class="clickable" @click="up"><td>↩︎ ..</td><td></td><td></td><td></td></tr>
        <tr v-for="d in dirs" :key="'d'+d.rel_path" class="clickable" @click="enter(d)">
          <td><div class="path">📂 {{ d.name }} <span class="sub">({{ d.file_count }})</span></div>
              <div class="summary" v-if="d.summary">{{ d.summary }}</div></td>
          <td class="sub">目录</td><td></td><td></td>
        </tr>
        <tr v-for="f in files" :key="'f'+f.resource_id" class="clickable" @click="open(f)">
          <td>
            <div style="display:flex;gap:10px;align-items:center">
              <img v-if="thumbable(f.name)" :src="'/api/files/'+f.resource_id+'/thumbnail?src='+cur+'&w=80'"
                   style="width:44px;height:44px;object-fit:cover;border-radius:6px;flex:none"
                   loading="lazy" @click.stop>
              <div>
                <div class="path">📄 {{ f.name }}</div>
                <div class="summary" v-if="f.summary">{{ f.summary.slice(0,140) }}</div>
              </div>
            </div>
          </td>
          <td class="sub">{{ fmtSize(f.size_bytes) }}</td>
          <td><span class="badge" :class="statusBadge(f.status)[0]">{{ statusBadge(f.status)[1] }}</span></td>
          <td class="sub">{{ f.category }}</td>
        </tr>
      </tbody>
    </table>
    <div class="hint" v-else-if="cur">此目录为空。</div>
    <div class="hint" v-else>尚无来源——请先到「来源」页注册一个本地目录或 WebDAV。</div>
  </div>`,
};

/* ────────────────────────── 来源管理 ────────────────────────── */
const SourcesView = {
  setup() {
    const list = ref([]);
    const showForm = ref(false);
    const testing = ref(false), probeResult = ref(null);
    const form = reactive({
      alias: "", protocol: "local", access_mode: "ro",
      root_path: "", url: "", username: "", password: "",
      label: "", scan_auto: false, scan_interval_min: 60,
      verify_ssl: true,
    });
    async function load() {
      const d = await api("/api/sources");
      list.value = d.sources || [];
    }
    async function add() {
      try {
        await api("/api/sources?test=true", { method: "POST", body: { ...form } });
        toast("来源已注册");
        showForm.value = false;
        Object.assign(form, { alias: "", protocol: "local", access_mode: "ro",
          root_path: "", url: "", username: "", password: "", label: "",
          scan_auto: false, scan_interval_min: 60 });
        await load();
      } catch (e) { toast("注册失败：" + e.message); }
    }
    async function test(sid) {
      try {
        const r = await api("/api/sources/" + sid + "/test", { method: "POST" });
        toast(r.ok ? "连通正常（" + r.ms + "ms）" : "失败：" + r.error);
      } catch (e) { toast(e.message); }
    }
    async function scan(sid) {
      try {
        const { job_id } = await api("/api/sources/" + sid + "/scan", { method: "POST" });
        toast("扫描已提交（任务 " + job_id + "）");
        pollJob(job_id);
      } catch (e) { toast(e.message); }
    }
    async function analyze(sid) {
      try {
        const { job_id } = await api("/api/sources/" + sid + "/analyze", { method: "POST" });
        toast("AI 分析已提交（任务 " + job_id + "），可在「任务」页查看进度");
      } catch (e) { toast(e.message); }
    }
    async function adopt(sid) {
      try {
        const { job_id } = await api("/api/sources/" + sid + "/adopt", { method: "POST" });
        toast("收编已提交（任务 " + job_id + "）");
        pollJob(job_id);
      } catch (e) { toast(e.message); }
    }
    async function pollJob(id) {
      const t = setInterval(async () => {
        try {
          const j = await api("/api/jobs/" + id);
          if (j.status === "completed") {
            clearInterval(t);
            const r = j.result || {};
            toast("扫描完成：新增 " + (r.added ?? "?") + " · 变更 " +
              (r.stale_source ?? "?") + " · 消失 " + (r.missing ?? "?"));
            await load();
          } else if (j.status === "failed") { clearInterval(t); toast("扫描失败：" + j.error); }
        } catch (e) { clearInterval(t); }
      }, 1500);
    }
    async function del(s) {
      if (!confirm("删除来源「" + s.alias + "」？" +
        (s.access_mode === "ro" ? "\n只读源：其入库知识将一并清除。" : ""))) return;
      try {
        await api("/api/sources/" + s.source_id, { method: "DELETE" });
        toast("已删除"); await load();
      } catch (e) { toast(e.message); }
    }
    async function toggle(s) {
      try {
        await api("/api/sources/" + s.source_id, {
          method: "PATCH", body: { enabled: !s.enabled } });
        await load();
      } catch (e) { toast(e.message); }
    }
    onMounted(load);
    return { list, showForm, form, add, test, scan, analyze, adopt, del, toggle,
             testing, probeResult, fmtSize, fmtTime };
  },
  template: `
  <div>
    <div class="card">
      <h2>🗂️ 知识来源
        <span class="spacer"></span>
        <button @click="showForm=!showForm">{{ showForm ? '收起' : '+ 注册来源' }}</button>
      </h2>
      <form class="grid" v-if="showForm" @submit.prevent="add" style="max-width:760px">
        <label>别名 *</label><input type="text" v-model="form.alias" required placeholder="如 home-nas-docs">
        <label>协议 *</label>
        <select v-model="form.protocol">
          <option value="local">local（本机目录/挂载盘）</option>
          <option value="webdav">WebDAV</option>
        </select>
        <label>访问属性 *</label>
        <select v-model="form.access_mode">
          <option value="ro">ro 只读知识库（绝不写源端）</option>
          <option value="rw">rw 可写（保留源端 .naskb 双写）</option>
        </select>
        <template v-if="form.protocol==='local'">
          <label>根路径 *</label><input type="text" v-model="form.root_path" placeholder="D:\\NAS\\docs 或挂载盘符路径">
        </template>
        <template v-else>
          <label>WebDAV URL *</label><input type="text" v-model="form.url" placeholder="https://192.168.5.2:5006/home/docs">
          <label>账号</label><input type="text" v-model="form.username">
          <label>密码</label><input type="password" v-model="form.password">
          <label>校验 SSL</label><input type="checkbox" v-model="form.verify_ssl">
        </template>
        <label>备注</label><input type="text" v-model="form.label">
        <label>自动扫描</label>
        <div class="row">
          <input type="checkbox" v-model="form.scan_auto">
          <input type="number" v-model="form.scan_interval_min" style="width:90px" min="5"> 分钟
        </div>
        <label></label>
        <div class="row"><button type="submit">测试并注册</button>
        <button type="button" class="ghost" @click="showForm=false">取消</button></div>
      </form>
      <p class="hint" v-if="!showForm">支持 local（本机目录、NFS/iSCSI 挂载点）与 WebDAV；SMB 直连在 V2。</p>
    </div>

    <div class="card">
      <table>
        <thead><tr>
          <th>别名</th><th>协议 / 根</th><th>模式</th><th>知识统计</th><th>最近扫描</th><th style="width:300px">操作</th>
        </tr></thead>
        <tbody>
          <tr v-for="s in list" :key="s.source_id">
            <td><b>{{ s.alias }}</b><div class="sub" v-if="s.label">{{ s.label }}</div>
              <span class="badge warn" v-if="!s.enabled">已停用</span></td>
            <td class="sub">{{ s.protocol }}<br>{{ s.protocol==='webdav' ? s.url : s.root_path }}</td>
            <td><span class="badge" :class="s.access_mode==='ro'?'accent':'ok'">{{ s.access_mode.toUpperCase() }}</span></td>
            <td class="sub" v-if="s.stats">
              文件 {{ s.stats.files }} · 最新 {{ s.stats.ok }} ·
              待更新 {{ s.stats.stale_source }} · 消失 {{ s.stats.missing_source }} ·
              已分析 {{ s.stats.analyzed }}
            </td>
            <td v-else class="sub">—</td>
            <td class="sub">{{ fmtTime(s.last_scan_at) }}</td>
            <td>
              <div class="row">
                <button class="small ghost" @click="test(s.source_id)">测试</button>
                <button class="small ghost" @click="scan(s.source_id)">扫描</button>
                <button class="small" @click="analyze(s.source_id)">AI 分析</button>
                <button class="small ghost" @click="adopt(s.source_id)" title="导入来源端已有的 .naskb 描述">收编</button>
                <button class="small ghost" @click="toggle(s)">{{ s.enabled ? '停用' : '启用' }}</button>
                <button class="small danger" @click="del(s)">删除</button>
              </div>
            </td>
          </tr>
          <tr v-if="!list.length"><td colspan="6" class="hint">还没有注册任何来源。</td></tr>
        </tbody>
      </table>
    </div>
  </div>`,
};

/* ────────────────────────── 任务中心 ────────────────────────── */
const JobsView = {
  setup() {
    const jobs = ref([]), timer = ref(null);
    async function load() {
      try {
        const d = await api("/api/jobs");
        jobs.value = (d.jobs || []).slice().reverse();
      } catch (e) { /* ignore */ }
    }
    onMounted(() => {
      load();
      timer.value = setInterval(load, 2000);
    });
    return { jobs, fmtTime, statusBadge };
  },
  template: `
  <div class="card">
    <h2>⚙️ 任务中心 <span class="sub">每 2 秒自动刷新</span></h2>
    <table v-if="jobs.length">
      <thead><tr><th>ID</th><th>类型</th><th>状态</th><th style="width:180px">进度</th><th>信息</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="j in jobs" :key="j.id">
          <td class="sub">{{ j.id }}</td>
          <td><span class="badge accent">{{ j.kind }}</span></td>
          <td><span class="badge" :class="{completed:'ok',running:'accent',failed:'bad',pending:''}[j.status]">{{ j.status }}</span></td>
          <td><div class="progress-outer"><div class="progress-inner" :style="{width: Math.round((j.progress||0)*100)+'%'}"></div></div></td>
          <td class="sub">
            <div v-if="j.message">{{ j.message }}</div>
            <div v-if="j.error" style="color:var(--bad)">{{ j.error }}</div>
            <details v-if="j.result"><summary class="sub">结果</summary>
              <pre class="sub" style="white-space:pre-wrap">{{ JSON.stringify(j.result, null, 2) }}</pre>
            </details>
          </td>
          <td class="sub">{{ fmtTime(j.created_at) }}</td>
        </tr>
      </tbody>
    </table>
    <div class="hint" v-else>暂无任务。扫描/AI 分析提交后会出现在这里。</div>
  </div>`,
};

/* ────────────────────────── 文件详情模态 ────────────────────────── */
const FileModal = {
  setup() {
    const visible = ref(false);
    const ctx = reactive({ rid: "", src: "" });
    const meta = ref(null), preview = ref(null), err = ref("");

    async function load() {
      meta.value = null; preview.value = null; err.value = "";
      visible.value = true;
      try {
        const qs = "src=" + encodeURIComponent(ctx.src);
        meta.value = await api("/api/files/" + ctx.rid + "?" + qs);
        preview.value = await api("/api/files/" + ctx.rid + "/preview?" + qs);
      } catch (e) { err.value = e.message; visible.value = true; }
    }
    window.addEventListener("open-file", (ev) => {
      ctx.rid = ev.detail.rid; ctx.src = ev.detail.src || "";
      load();
    });
    return { visible, ctx, meta, preview, err, fmtSize, statusBadge };
  },
  template: `
  <div class="modal-mask" v-if="visible" @click.self="visible=false">
    <div class="modal">
      <div class="head">
        <b style="word-break:break-all">{{ meta?.resource?.name || '文件' }}</b>
        <span class="badge" :class="statusBadge(meta?.resource?.status)[0]" v-if="meta">{{ statusBadge(meta?.resource?.status)[1] }}</span>
        <span class="spacer"></span>
        <a v-if="meta" class="button ghost small" style="padding:6px 12px;border:1px solid var(--line);border-radius:8px;text-decoration:none;color:var(--ink)"
           :href="meta.download_url" target="_blank">下载</a>
        <button class="ghost small" @click="visible=false">关闭 ✕</button>
      </div>
      <div class="body">
        <div class="error" v-if="err">{{ err }}</div>
        <template v-if="preview">
          <div class="viewer" v-if="preview.viewable==='image'">
            <img :src="preview.url" alt="">
          </div>
          <div class="viewer" v-else-if="preview.viewable==='pdf'">
            <iframe :src="preview.url"></iframe>
          </div>
          <div class="viewer" v-else-if="preview.viewable==='video'">
            <video controls preload="metadata" :src="preview.url"></video>
          </div>
          <div class="viewer" v-else-if="preview.viewable==='audio'">
            <audio controls style="width:100%" :src="preview.url"></audio>
          </div>
          <div class="viewer" v-else-if="preview.viewable==='text'">
            <pre class="text">{{ preview.content }}</pre>
          </div>
          <div class="viewer" v-else-if="preview.viewable==='parsed'">
            <iframe :src="preview.parsed_url" style="width:100%;height:72vh;border:1px solid var(--line);border-radius:8px"></iframe>
          </div>
          <div class="viewer" v-else-if="preview.viewable==='html'">
            <iframe sandbox style="width:100%;height:72vh;border:1px solid var(--line);border-radius:8px"
                    :srcdoc="preview.content"></iframe>
          </div>
          <div v-else>
            <div class="hint">⚠️ 该类型暂不支持在线查看（{{ preview.reason }}），可下载后本地打开。</div>
          </div>
        </template>
        <div class="hint" v-else-if="!err">加载预览中…</div>

        <div class="card" style="margin-top:16px;margin-bottom:0" v-if="meta">
          <h2>🧠 知识元数据</h2>
          <dl class="kv">
            <dt>路径</dt><dd>{{ meta.resource.rel_path }}</dd>
            <dt>分类</dt><dd>{{ meta.resource.category || '—' }}</dd>
            <dt>标签</dt><dd>{{ (meta.resource.tags||[]).join('、') || '—' }}</dd>
            <dt>摘要</dt><dd>{{ meta.resource.summary || '—' }}</dd>
            <dt>内容描述</dt><dd>{{ meta.resource.content_description || '—' }}</dd>
            <dt>指纹</dt><dd class="sub">{{ meta.resource.hash_algorithm || '未计算' }}
              <code>{{ (meta.resource.file_hash||'').slice(0,16) }}</code></dd>
            <dt>大小 / 时间</dt><dd>{{ fmtSize(meta.resource.size_bytes) }} · mtime {{ fmtTime(meta.resource.mtime) }}</dd>
            <dt>分析时间</dt><dd>{{ fmtTime(meta.resource.analyzed_at) }}</dd>
          </dl>
        </div>
      </div>
    </div>
  </div>`,
};

/* ────────────────────────── 根组件 ────────────────────────── */
const App = {
  components: { SearchView, BrowseView, SourcesView, JobsView, FileModal },
  setup() {
    const views = { search: SearchView, browse: BrowseView,
                    sources: SourcesView, jobs: JobsView };
    const cur = computed(() => views[state.route] || SearchView);
    const tokenInput = ref(state.token);
    function go(r) {
      state.route = r;
      location.hash = "#/" + r;
    }
    function saveToken() {
      state.token = tokenInput.value.trim();
      localStorage.setItem("naskb_token", state.token);
      toast(state.token ? "令牌已保存" : "令牌已清除");
    }
    onMounted(async () => {
      window.addEventListener("hashchange", () => {
        state.route = location.hash.replace(/^#\/?/, "") || "search";
      });
      try {
        const c = await api("/api/config/public");
        state.authRequired = c.auth_required;
        state.anonymousRead = c.anonymous_read;
      } catch (e) { /* 服务不可达时静默 */ }
    });
    return { state, cur, go, tokenInput, saveToken };
  },
  template: `
  <header>
    <div class="logo">📚 NASKB 知识库系统<small>v0.1</small></div>
    <nav>
      <a :class="{active: state.route==='search'}" @click="go('search')">检索问答</a>
      <a :class="{active: state.route==='browse'}" @click="go('browse')">浏览</a>
      <a :class="{active: state.route==='sources'}" @click="go('sources')">来源</a>
      <a :class="{active: state.route==='jobs'}" @click="go('jobs')">任务</a>
    </nav>
    <span class="spacer"></span>
    <details v-if="state.authRequired" style="position:relative">
      <summary class="badge" :class="state.token ? 'ok' : 'warn'">{{ state.token ? '🔑 已配置令牌' : '🔒 需要令牌' }}</summary>
      <div class="card" style="position:absolute;right:0;top:30px;width:320px;z-index:60">
        <div class="row">
          <input type="password" v-model="tokenInput" placeholder="管理员 Bearer token" style="flex:1">
          <button class="small" @click="saveToken">保存</button>
        </div>
        <p class="hint">config.toml [server] tokens 中配置；仅存于本浏览器。</p>
      </div>
    </details>
  </header>
  <main><component :is="cur"></component></main>
  <file-modal></file-modal>
  <div class="toast" v-if="state.toast">{{ state.toast }}</div>`,
};

createApp(App).mount("#app");
