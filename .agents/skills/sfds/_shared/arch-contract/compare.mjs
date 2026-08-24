// compare.mjs — 架构契约比较器（纯函数，无 IO，技术中性）
// 规范：.agents/skills/sfds/_shared/arch-contract-spec.md（v0.1）
// 输入：契约对象 + 事实对象 + 已解析的 design:// 指针值 + 今日日期
// 输出：{ summary, issues, exitCode }，报告结构遵循 _shared/consistency-check-format.md

const SEVERITY_DEFAULT = {
  'dependency-direction': 'high',
  'reference-whitelist': 'high',
  'ownership': 'high',
  'value-domain': 'medium',
  'set-relation': 'high',
};

// ---------- 分组匹配（§2.2）----------

function segs(s) { return String(s).split(/[./]+/).filter(Boolean); }

function matchSegs(pat, unit) {
  if (pat.length === 0) return unit.length === 0;
  const head = pat[0];
  const rest = pat.slice(1);
  if (head === '**') {
    for (let i = 0; i <= unit.length; i++) {
      if (matchSegs(rest, unit.slice(i))) return true;
    }
    return false;
  }
  if (unit.length === 0) return false;
  if (head === '*') return matchSegs(rest, unit.slice(1));
  return head === unit[0] && matchSegs(rest, unit.slice(1));
}

export function matchPattern(pattern, unitPath) {
  return matchSegs(segs(pattern), segs(unitPath));
}

export function matchAny(patterns, unitPath) {
  return (patterns || []).some((p) => matchPattern(p, unitPath));
}

function normKey(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]/g, '');
}

// unit → 分组名（未命中返回 null）
export function groupOf(contract, unitPath) {
  const groups = contract.groups || {};
  for (const name of Object.keys(groups)) {
    if (matchAny(groups[name], unitPath)) return name;
  }
  return null;
}

// ---------- 工具 ----------

// 指针值 → 条目列表。数组原样；对象按 collectKey 收集各模块子数组（§5.2 桥接）。
// 字符串条目包装为 { value }，保留 _module 供桥接。
function collectEntries(value, collectKey) {
  if (value == null) return [];
  if (Array.isArray(value)) {
    return value.map((e) => (typeof e === 'string' || typeof e === 'number' ? { value: String(e) } : { ...e }));
  }
  const out = [];
  for (const mod of Object.keys(value)) {
    const sub = value[mod];
    if (Array.isArray(sub)) {
      sub.forEach((e) => out.push(typeof e === 'string' ? { _module: mod, value: e } : { ...e, _module: mod }));
    } else if (sub && Array.isArray(sub[collectKey])) {
      sub[collectKey].forEach((e) =>
        out.push(typeof e === 'string' ? { _module: mod, value: e } : { ...e, _module: mod })
      );
    }
  }
  return out;
}

function ev(fact) {
  const e = fact.evidence || {};
  return `${e.file || fact.unit || '?'}${e.line != null ? ':' + e.line : ''}`;
}

function mkIssue(rule, fact, detail, suggestion, severityOverride) {
  return {
    severity: severityOverride || SEVERITY_DEFAULT[rule.type] || 'medium',
    type: 'arch_rule_violation',
    source: 'architecture-to-code',
    ref_path: ev(fact),
    ruleId: rule.id,
    enforcement: rule.enforcement,
    debtMatched: false,
    _unit: fact.unit || '',
    _key: fact.key || '',
    detail,
    suggestion: suggestion || rule.remediationHint || `依据：${rule.rationale}`,
  };
}

// ---------- 五种谓词 ----------

function checkDependencyDirection(rule, ctx) {
  const issues = [];
  for (const f of ctx.facts.dependency || []) {
    if (!matchAny(rule.from, f.from)) continue;
    if (!matchAny(rule.forbid, f.to)) continue;
    if (rule.kinds && !rule.kinds.includes(f.kind)) continue;
    issues.push(
      mkIssue(rule, f, `${f.from} → ${f.to}（${f.kind}）违反依赖方向：${rule.rationale}`)
    );
  }
  return issues;
}

function normMap(mg) {
  // 桥接表键归一化：兼容 slug 键（task-management）与显示名键（TaskManagement）
  const out = {};
  for (const k of Object.keys(mg || {})) out[normKey(k)] = mg[k];
  return out;
}

function checkReferenceWhitelist(rule, ctx) {
  const issues = [];
  const entries = collectEntries(ctx.resolved[rule.whitelist], rule.collectKey || 'crossModuleCalls');
  const mg = normMap(rule.moduleGroups);
  const pairs = [];
  for (const e of entries) {
    const fromG = e._module != null ? mg[normKey(e._module)] || null : null;
    const toG = mg[normKey(e.target)] || null;
    pairs.push({ fromG, toG, via: e.via || null });
  }
  const allowed = (fromG, toG) =>
    pairs.some((p) => p.toG === toG && (p.fromG === null || p.fromG === fromG));
  for (const f of ctx.facts.reference || []) {
    const fromG = groupOf(ctx.contract, f.unit);
    const toG = groupOf(ctx.contract, f.target);
    if (rule.from && !rule.from.includes(fromG)) continue; // 作用域限定
    if (rule.ignoreToGroups && toG && rule.ignoreToGroups.includes(toG)) continue; // 目标豁免（如底层基础设施客户端）
    if (rule.allowToGroups && toG && rule.allowToGroups.includes(toG)) continue; // 分组级许可（上游 layering dependsOn 已声明的层间依赖）
    if (!fromG || !toG || fromG === toG) continue;
    if (allowed(fromG, toG)) continue;
    issues.push(
      mkIssue(rule, f, `${f.unit} → ${f.target}（via ${f.via || '?'}）的跨组引用未在白名单（${fromG} → ${toG}）`)
    );
  }
  return issues;
}

function checkOwnership(rule, ctx) {
  const issues = [];
  const entries = collectEntries(ctx.resolved[rule.ownership], rule.collectKey || 'ownsEntities');
  const mg = normMap(rule.moduleGroups);
  const assetOwner = {};
  let unregistered = 0;
  const ownerOf = (asset) => {
    if (!(asset in assetOwner)) {
      const hit = entries.find((e) => e.value === asset || e.asset === asset || e.name === asset);
      assetOwner[asset] = hit ? mg[normKey(hit._module)] || null : null;
    }
    return assetOwner[asset];
  };
  for (const f of ctx.facts.assetRef || []) {
    if (f.assetKind !== rule.assetKind) continue;
    const owner = ownerOf(f.asset);
    if (owner == null) { unregistered++; continue; }
    const ug = groupOf(ctx.contract, f.unit);
    if (!ug) continue;
    if (ug !== owner) {
      issues.push(
        mkIssue(rule, f, `${f.unit} 直接引用资产 ${f.asset}（属主 ${owner}，引用方分组 ${ug}）——跨组访问须走属主服务接口`)
      );
    }
  }
  ctx.counters.unregisteredAssets += unregistered;
  return issues;
}

function checkValueDomain(rule, ctx) {
  const issues = [];
  const vd = (ctx.contract.valueDomains || {})[rule.domain] || {};
  const allow = rule.allowLiteralIn || (vd.constantsUnit ? [vd.constantsUnit] : []);
  for (const f of ctx.facts.literal || []) {
    if (f.domain !== rule.domain) continue;
    if (matchAny(allow, f.unit)) continue;
    if (rule.enforcement === 'heuristic') {
      if (f.inComparison) {
        issues.push(
          mkIssue(rule, f, `${f.unit} 在比较上下文中使用裸字面量 "${f.value}"（应引用 ${vd.constantsUnit || '命名常量'}）`, null, 'low')
        );
      }
      continue;
    }
    issues.push(mkIssue(rule, f, `${f.unit} 使用裸字面量 "${f.value}"（值域 ${rule.domain} 唯一权威定义在 ${vd.constantsUnit || '命名常量'}）`));
  }
  return issues;
}

function normalizeDeclared(value, declaredKey, declaredKeyFmt) {
  if (value == null) return [];
  let arr;
  if (Array.isArray(value)) arr = value;
  else if (typeof value === 'object') arr = Object.keys(value); // 对象根 → 键集合（键即声明项）
  else arr = [value];
  return arr
    .map((it) => {
      if (typeof it === 'string') return it;
      if (it && typeof it === 'object') {
        if (declaredKeyFmt) {
          // 组合键（如 "method path"）：字段以空格拼接后统一小写
          return declaredKeyFmt
            .split(/\s+/)
            .map((f) => it[f])
            .filter((v) => v != null)
            .join(' ')
            .toLowerCase();
        }
        const v = it[declaredKey || 'key'] ?? it.name ?? it.event ?? it.id ?? null;
        return v == null ? null : String(v);
      }
      return null;
    })
    .filter((k) => typeof k === 'string' && k.length > 0);
}

function checkSetRelation(rule, ctx) {
  const issues = [];
  const declared = rule.declaredInline
    ? normalizeDeclared(rule.declaredInline, rule.declaredKey, rule.declaredKeyFmt)
    : normalizeDeclared(ctx.resolved[rule.declared], rule.declaredKey, rule.declaredKeyFmt);
  const actual = [...new Set((ctx.facts.registry || [])
    .filter((r) => r.set === rule.actualSet)
    .map((r) => String(r.key).toLowerCase()))]; // keyStyle 归一化兜底：大小写不敏感比较
  const mode = rule.mustMatch || 'equal';
  const missing = declared.filter((k) => !actual.includes(k));
  const extra = actual.filter((k) => !declared.includes(k));
  if ((mode === 'equal' || mode === 'declared-in-actual') && missing.length) {
    issues.push(
      mkIssue(rule, { evidence: { file: `set:${rule.actualSet}` } },
        `声明集合有 ${missing.length} 项未在实际集合中出现：${missing.slice(0, 10).join('、')}${missing.length > 10 ? '…' : ''}`)
    );
  }
  if ((mode === 'equal' || mode === 'actual-in-declared') && extra.length) {
    issues.push(
      mkIssue(rule, { evidence: { file: `set:${rule.actualSet}` } },
        `实际集合有 ${extra.length} 项无声明来源：${extra.slice(0, 10).join('、')}${extra.length > 10 ? '…' : ''}`, null, 'medium')
    );
  }
  return issues;
}

const CHECKERS = {
  'dependency-direction': checkDependencyDirection,
  'reference-whitelist': checkReferenceWhitelist,
  'ownership': checkOwnership,
  'value-domain': checkValueDomain,
  'set-relation': checkSetRelation,
};

// ---------- 主入口 ----------

export function compare({ contract, facts, resolved, today }) {
  const ctx = {
    contract,
    facts: facts.facts || {},
    resolved: resolved || {},
    counters: { unregisteredAssets: 0 },
  };
  let issues = [];
  let rulesChecked = 0;
  const activeRules = (contract.rules || []).filter((r) => r.enforcement !== 'review');
  for (const rule of activeRules) {
    const checker = CHECKERS[rule.type];
    if (!checker) continue;
    rulesChecked++;
    issues.push(...checker(rule, ctx));
  }

  // knownDebts 匹配（§8）：ruleId 相同 + scope 匹配证据（file / unit / key）→ 降级 WARN
  const todayStr = today || new Date().toISOString().slice(0, 10);
  const debts = contract.knownDebts || [];
  let debtsActive = 0;
  for (const debt of debts) {
    if (debt.expires >= todayStr) debtsActive++;
    for (const iss of issues) {
      if (iss.ruleId !== debt.ruleId || iss.debtMatched) continue;
      const file = (iss.ref_path || '').split(':')[0];
      const scopeHit =
        matchPattern(debt.scope, file) ||
        matchPattern(debt.scope, iss._unit || '') ||
        matchPattern(debt.scope, iss._key || '');
      if (!scopeHit) continue;
      if (debt.expires >= todayStr) {
        iss.debtMatched = true;
        iss.severity = 'low';
        iss.detail += `［已登记债务 ${debt.ruleId}/${debt.issue}，宽限至 ${debt.expires}］`;
      } else {
        iss.detail += `［债务 ${debt.ruleId}/${debt.issue} 已于 ${debt.expires} 到期，恢复拦截］`;
      }
    }
  }

  const count = (s) => issues.filter((i) => i.severity === s).length;
  const summary = {
    end_slug: 'arch-contract',
    producer: 'backend-architecture-design',
    total_scanned: (facts.units || []).length,
    total_issues: issues.length,
    high: count('high'),
    medium: count('medium'),
    low: count('low'),
    rulesChecked,
    reviewLedgerCount: (contract.reviewLedger || []).length,
    debtsTotal: debts.length,
    debtsActive,
    unmatchedUnits: (facts.units || []).filter((u) => groupOf(contract, u.path) === null).length,
    unregisteredAssets: ctx.counters.unregisteredAssets,
  };
  const exitCode = issues.some((i) => i.enforcement === 'mechanical' && !i.debtMatched) ? 1 : 0;
  return { summary, issues, exitCode };
}
