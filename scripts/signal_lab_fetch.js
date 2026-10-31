// scripts/signal_lab_fetch.js
// 用法：在已登录的飞书「策略库」标签页里执行（控制台或经 CDP evaluate_script）：
//   const cases = await signalLabFetch();
// 然后把 cases 保存为 JSON 文件交给 scripts/fetch_signal_lab.py 落盘。
const BASE = "M3Yvbt032aq8smsSi1BcrLisn9g";
const CASE_TABLE = "tblW6XBSpDRg3Q44";

async function gzipDecode(b64) {
  const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const stream = new Blob([bin]).stream().pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(stream).text());
}

async function fetchTableBlob(tableId) {
  const url =
    `/space/api/v1/bitable/${BASE}/clientvars?tableID=${tableId}&viewID=` +
    `&recordLimit=200&ondemandLimit=200&needBase=true&viewLazyLoad=true` +
    `&ondemandVer=2&noMissCS=true&optimizationFlag=1&removeFmlExtra=true`;
  const d = (await fetch(url, { credentials: "include" }).then((r) => r.json())).data;
  return gzipDecode(d.table);
}

function cellText(value) {
  if (value == null) return "";
  if (Array.isArray(value)) return value.map((v) => (v && v.text) || "").join("");
  if (typeof value === "object" && "text" in value) return String(value.text ?? "");
  return String(value);
}

// signal_name 是链接字段：解析其目标表，建 recordId -> 主键字段文本 的映射
async function linkedNameMap(fieldMap, fieldName) {
  const field = Object.values(fieldMap).find((f) => f.name === fieldName);
  if (!field) return {};
  const prop = field.property || {};
  const targetTable = prop.tableId || prop.targetTableId || prop.foreignTableId;
  if (!targetTable) return {};
  const t = await fetchTableBlob(targetTable);
  const pk = t.primaryKey;
  const map = {};
  for (const [rid, rec] of Object.entries(t.recordMap || {})) {
    const cell = rec[pk];
    map[rid] = cellText(cell && cell.value);
  }
  return map;
}

window.signalLabFetch = async function () {
  const table = await fetchTableBlob(CASE_TABLE);
  const fm = table.fieldMap || {};
  const find = (name) => Object.values(fm).find((f) => f.name === name);
  // fieldMap 以字段 id 为 key（字段对象里没有 id 属性）
  const byName = Object.fromEntries(Object.entries(fm).map(([fid, f]) => [f.name, fid]));

  const signalOpts = {};
  const sf = find("signal");
  for (const o of (sf && sf.property && sf.property.options) || []) signalOpts[o.id] = o.name;
  const strategyNames = await linkedNameMap(fm, "signal_name");

  const out = [];
  for (const [rid, rec] of Object.entries(table.recordMap || {})) {
    const v = (id) => { const c = rec[id]; return c ? c.value : undefined; };
    const dateVal = v(byName["date"]);
    // 链接字段（signal_name）的值是 record id 字符串数组，直接取第一个 id
    const linkVal = v(byName["signal_name"]);
    const linkId = Array.isArray(linkVal) ? String(linkVal[0] || "") : cellText(linkVal);
    out.push({
      id: rid,
      name: cellText(v(byName["名称"])) || "未命名",
      date: typeof dateVal === "number" ? new Date(dateVal).toISOString().slice(0, 10) : cellText(dateVal),
      code: cellText(v(byName["symbol_id"])),
      signal: signalOpts[cellText(v(byName["signal"]))] || cellText(v(byName["signal"])) || "",
      strategy: strategyNames[linkId] || "",
      info: cellText(v(byName["info"])),
      note: cellText(v(byName["注意点"])),
    });
  }
  return out;
};
