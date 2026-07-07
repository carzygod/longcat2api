ADMIN_HTML = r"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>LONGCAT-WEB-01 Admin</title>
  <style>
    :root{
      --bg:#050913;
      --panel:#0d1422;
      --panel-2:#111b2b;
      --panel-3:#162235;
      --line:rgba(116,232,255,.14);
      --line-2:rgba(255,255,255,.08);
      --text:#edf7ff;
      --muted:#8ba2b7;
      --dim:#5f758b;
      --cyan:#42e8ff;
      --blue:#5a7dff;
      --violet:#a565ff;
      --green:#70f0b2;
      --orange:#ffbd66;
      --red:#ff6f91;
      --shadow:0 24px 80px rgba(0,0,0,.42);
      --glow:0 0 0 1px rgba(66,232,255,.22),0 18px 50px rgba(38,151,255,.16);
      --grad:linear-gradient(135deg,rgba(66,232,255,.96),rgba(90,125,255,.96) 55%,rgba(165,101,255,.96));
      --soft:linear-gradient(135deg,rgba(66,232,255,.10),rgba(90,125,255,.06) 58%,rgba(165,101,255,.10));
    }
    *{box-sizing:border-box}
    body{
      margin:0;
      min-height:100vh;
      color:var(--text);
      background:
        radial-gradient(circle at 18% 8%,rgba(66,232,255,.16),transparent 28%),
        radial-gradient(circle at 78% 0%,rgba(165,101,255,.14),transparent 25%),
        linear-gradient(145deg,#03050b 0%,#07101d 44%,#090814 100%);
      font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;
    }
    button,input,textarea,select{font:inherit}
    button{cursor:pointer}
    .app{display:grid;grid-template-columns:264px 1fr;min-height:100vh}
    .sidebar{
      position:sticky;top:0;height:100vh;padding:22px 18px;
      border-right:1px solid var(--line);
      background:linear-gradient(180deg,rgba(7,13,25,.95),rgba(9,13,24,.86));
      backdrop-filter:blur(18px);
    }
    .brand{display:flex;align-items:center;gap:12px;margin-bottom:26px}
    .brand-mark{
      width:44px;height:44px;border-radius:16px;display:grid;place-items:center;
      background:var(--grad);color:#04101b;font-weight:900;font-size:19px;
      box-shadow:0 15px 42px rgba(66,232,255,.22);
    }
    .brand-title{font-size:18px;font-weight:900;letter-spacing:.2px}
    .brand-sub{font-size:12px;color:var(--muted);margin-top:3px}
    .nav{display:grid;gap:9px}
    .nav button{
      width:100%;border:1px solid transparent;background:transparent;color:var(--muted);
      border-radius:16px;padding:13px 14px;display:flex;align-items:center;gap:11px;
      text-align:left;transition:.22s ease;
    }
    .nav button:hover{color:var(--text);background:rgba(255,255,255,.04);border-color:var(--line-2)}
    .nav button.active{color:var(--text);background:var(--soft);border-color:rgba(66,232,255,.28);box-shadow:var(--glow)}
    .nav-ico{width:26px;height:26px;border-radius:10px;display:grid;place-items:center;background:rgba(255,255,255,.06)}
    .side-foot{
      position:absolute;left:18px;right:18px;bottom:18px;padding:14px;border-radius:18px;
      background:rgba(255,255,255,.04);border:1px solid var(--line-2);color:var(--muted);font-size:12px;
    }
    .main{padding:26px;min-width:0}
    .topbar{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:20px}
    h1{margin:0;font-size:26px;line-height:1.2}
    h2,h3{margin:0}
    .subline{margin-top:7px;color:var(--muted);font-size:13px}
    .actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
    .btn{
      border:1px solid var(--line-2);border-radius:14px;padding:10px 13px;
      background:rgba(255,255,255,.055);color:var(--text);font-weight:750;
      transition:.18s ease;display:inline-flex;align-items:center;gap:8px;
    }
    .btn:hover{transform:translateY(-1px);border-color:rgba(66,232,255,.34)}
    .btn.primary{background:var(--grad);color:#04101b;border:0;box-shadow:0 16px 42px rgba(66,232,255,.18)}
    .btn.danger{color:#ffdbe3;border-color:rgba(255,111,145,.28);background:rgba(255,111,145,.09)}
    .btn.ghost{background:transparent}
    .btn:disabled{opacity:.48;cursor:not-allowed;transform:none}
    .metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:16px}
    .card{
      background:linear-gradient(180deg,rgba(17,27,43,.94),rgba(9,16,28,.94));
      border:1px solid var(--line);border-radius:22px;padding:18px;box-shadow:var(--shadow);
    }
    .metric-label{color:var(--muted);font-size:12px}
    .metric-value{font-size:30px;font-weight:900;margin-top:7px;letter-spacing:.2px}
    .metric-meta{color:var(--dim);font-size:12px;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .split{display:grid;grid-template-columns:minmax(340px,420px) 1fr;gap:16px}
    .account-list{display:grid;gap:12px;max-height:calc(100vh - 265px);overflow:auto;padding-right:4px}
    .account-card{
      border:1px solid var(--line-2);border-radius:18px;padding:14px;background:rgba(255,255,255,.035);
      transition:.18s ease;
    }
    .account-card:hover,.account-card.active{border-color:rgba(66,232,255,.36);background:var(--soft);box-shadow:var(--glow)}
    .account-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
    .account-name{font-weight:900}
    .mono{font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace}
    .account-id,.hint{font-size:12px;color:var(--dim);margin-top:4px;word-break:break-all}
    .badges{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}
    .badge{
      display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:5px 9px;
      font-size:12px;font-weight:800;border:1px solid var(--line-2);background:rgba(255,255,255,.055);color:var(--muted);
    }
    .badge.ready{color:#b8ffd9;background:rgba(112,240,178,.09);border-color:rgba(112,240,178,.25)}
    .badge.hot{color:#ccf8ff;background:rgba(66,232,255,.09);border-color:rgba(66,232,255,.25)}
    .badge.warn{color:#ffdeaa;background:rgba(255,189,102,.10);border-color:rgba(255,189,102,.25)}
    .badge.error{color:#ffc7d2;background:rgba(255,111,145,.10);border-color:rgba(255,111,145,.25)}
    .quota-row{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:12px}
    .quota-pill{border:1px solid var(--line-2);border-radius:14px;padding:10px;background:rgba(0,0,0,.12)}
    .quota-pill strong{display:block;font-size:13px}
    .quota-pill small{display:block;color:var(--dim);margin-top:3px;font-size:11px}
    .detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:15px 0}
    .kv{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid var(--line-2);padding:10px 0;color:var(--muted)}
    .kv span:last-child{color:var(--text);text-align:right;word-break:break-all}
    .form{display:grid;gap:12px}
    label{display:grid;gap:7px;color:var(--muted);font-size:12px;font-weight:750}
    input,textarea,select{
      width:100%;border:1px solid var(--line-2);border-radius:15px;
      background:rgba(2,6,13,.78);color:var(--text);padding:12px 13px;outline:none;
    }
    textarea{min-height:118px;resize:vertical;line-height:1.55}
    input:focus,textarea:focus,select:focus{border-color:rgba(66,232,255,.42);box-shadow:0 0 0 3px rgba(66,232,255,.08)}
    pre,.output{
      margin:0;white-space:pre-wrap;word-break:break-word;max-height:390px;overflow:auto;
      background:rgba(0,0,0,.22);border:1px solid var(--line-2);border-radius:16px;padding:14px;color:#dcecff;
    }
    .models{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
    .table{width:100%;border-collapse:collapse}
    .table th,.table td{border-bottom:1px solid var(--line-2);padding:12px;text-align:left;font-size:13px;vertical-align:top}
    .table th{color:var(--muted);font-size:12px}
    .empty{color:var(--dim);padding:28px;text-align:center;border:1px dashed var(--line-2);border-radius:18px}
    .modal-mask{position:fixed;inset:0;background:rgba(1,4,10,.74);backdrop-filter:blur(10px);display:none;align-items:center;justify-content:center;padding:22px;z-index:20}
    .modal-mask.open{display:flex}
    .modal{width:min(920px,100%);max-height:88vh;overflow:auto;background:#0b1320;border:1px solid var(--line);border-radius:24px;box-shadow:0 28px 110px rgba(0,0,0,.6);padding:20px}
    .modal-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px}
    .modal img{max-width:100%;border-radius:18px;border:1px solid var(--line-2);background:#fff}
    .toast{position:fixed;right:22px;bottom:22px;background:#101b2b;border:1px solid var(--line);border-radius:15px;padding:12px 14px;box-shadow:var(--shadow);display:none;z-index:30}
    .toast.show{display:block}
    @media (max-width:1100px){.app{grid-template-columns:1fr}.sidebar{position:relative;height:auto}.side-foot{position:relative;left:auto;right:auto;bottom:auto;margin-top:16px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.split{grid-template-columns:1fr}}
    @media (max-width:680px){.main{padding:16px}.metrics{grid-template-columns:1fr}.detail-grid{grid-template-columns:1fr}.topbar{align-items:flex-start;flex-direction:column}}
  </style>
</head>
<body>
<div id="app" class="app">
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">LC</div>
      <div>
        <div class="brand-title">LONGCAT-WEB-01</div>
        <div class="brand-sub">LongCat Web Reverse Proxy</div>
      </div>
    </div>
    <nav class="nav" id="nav"></nav>
    <div class="side-foot">
      <div class="mono" id="sideBase"></div>
      <div style="margin-top:8px">当前版本采用单浏览器账号池门面，并保持 gen2api 系列管理台交互习惯。</div>
    </div>
  </aside>
  <main class="main">
    <div class="topbar">
      <div>
        <h1 id="pageTitle">账号池</h1>
        <div class="subline" id="pageSub">维护 LongCat 登录态、Cookie 和浏览器运行状态</div>
      </div>
      <div class="actions">
        <button class="btn ghost" onclick="refreshAll()">刷新</button>
        <button class="btn primary" onclick="openCookieModal()">导入 Cookie</button>
        <button class="btn" onclick="startQr('default')">扫码登录</button>
      </div>
    </div>

    <section id="tab-accounts" class="tab-panel">
      <div class="metrics" id="metrics"></div>
      <div class="split">
        <div class="card">
          <div class="account-list" id="accountList"></div>
        </div>
        <div class="card" id="accountDetail"></div>
      </div>
    </section>

    <section id="tab-test" class="tab-panel" style="display:none">
      <div class="split">
        <div class="card">
          <h3>接口操练场</h3>
          <div class="subline">请求会直接走本服务的 OpenAI 兼容接口；只有拿到真实媒体 URL 才算成功。</div>
          <div class="form" style="margin-top:16px">
            <label>账号
              <select id="testAccount"><option value="default">LongCat 默认账号 / default</option></select>
            </label>
            <label>模型
              <select id="testModel">
                <option value="longcat-image">longcat-image / 文生图</option>
                <option value="longcat-video">longcat-video / 文生视频</option>
                <option value="longcat-video-fast">longcat-video-fast / 视频别名</option>
              </select>
            </label>
            <label>Prompt
              <textarea id="testPrompt">生成一只可爱的猫咪图片，柔和光线，高清细节。</textarea>
            </label>
            <button class="btn primary" id="runTestBtn" onclick="runTest()">发送测试</button>
          </div>
        </div>
        <div class="card">
          <h3>测试输出</h3>
          <div class="subline">失败时这里会保留 provider 返回的错误，便于排障。</div>
          <pre id="testOutput" style="margin-top:16px">等待测试...</pre>
        </div>
      </div>
    </section>

    <section id="tab-logs" class="tab-panel" style="display:none">
      <div class="card">
        <div class="actions" style="justify-content:space-between;margin-bottom:10px">
          <div>
            <h3>请求日志</h3>
            <div class="subline">最近 200 条本服务请求，不记录敏感 Cookie。</div>
          </div>
          <button class="btn" onclick="loadLogs()">刷新日志</button>
        </div>
        <div id="logs"></div>
      </div>
    </section>

    <section id="tab-system" class="tab-panel" style="display:none">
      <div class="split">
        <div class="card">
          <h3>系统信息</h3>
          <div id="systemInfo" style="margin-top:12px"></div>
        </div>
        <div class="card">
          <h3>平台密钥</h3>
          <div class="subline">NewAPI 或调用方使用 Bearer Token 访问本服务。</div>
          <div class="form" style="margin-top:16px">
            <label>LONGCAT_API_KEY
              <input id="serviceKey" autocomplete="off" />
            </label>
            <div class="actions">
              <button class="btn primary" onclick="saveServiceKey()">保存密钥</button>
              <button class="btn" onclick="copyApiBase()">复制 API Base</button>
            </div>
          </div>
          <div class="models" id="modelBadges"></div>
        </div>
      </div>
    </section>
  </main>
</div>

<div id="modalMask" class="modal-mask">
  <div class="modal">
    <div class="modal-head">
      <div>
        <h3 id="modalTitle">Modal</h3>
        <div class="subline" id="modalSub"></div>
      </div>
      <button class="btn ghost" onclick="closeModal()">关闭</button>
    </div>
    <div id="modalBody"></div>
  </div>
</div>
<div id="toast" class="toast"></div>

<script>
const KEY="__API_KEY__";
const API_BASE=location.origin;
const tabs=[
  {key:"accounts",name:"账号池",sub:"维护 LongCat 登录态、Cookie 和浏览器运行状态",icon:"◎"},
  {key:"test",name:"接口测试",sub:"快速验证文生图与文生视频路径",icon:"▣"},
  {key:"logs",name:"请求日志",sub:"查看最近请求和失败状态",icon:"≡"},
  {key:"system",name:"系统",sub:"查看路径、密钥和模型列表",icon:"⚙"}
];
const state={tab:"accounts",accounts:[],selectedId:"default",system:{},models:[],logs:[],serviceKey:KEY,busy:false};

function authHeaders(json=true){
  const headers={Authorization:"Bearer "+state.serviceKey,"X-API-Key":state.serviceKey};
  if(json)headers["Content-Type"]="application/json";
  return headers;
}
async function api(path,options={}){
  const url=path+(path.includes("?")?"&":"?")+"key="+encodeURIComponent(state.serviceKey);
  const res=await fetch(url,{...options,headers:{...authHeaders(options.body!==undefined),...(options.headers||{})}});
  const text=await res.text();
  let data;try{data=JSON.parse(text)}catch{data=text}
  if(!res.ok)throw new Error(typeof data==="string"?data:JSON.stringify(data,null,2));
  return data;
}
function esc(value){return String(value??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]))}
function fmt(value){return value===undefined||value===null||value===""?"--":value}
function statusBadge(account){
  if(account.runtime?.ready)return '<span class="badge ready">ready</span>';
  if(account.runtime?.hot)return '<span class="badge warn">待登录</span>';
  return '<span class="badge error">stopped</span>';
}
function toast(text){const el=document.getElementById("toast");el.textContent=text;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2600)}
function setBusy(on){state.busy=on;document.querySelectorAll("button").forEach(btn=>btn.disabled=on&&btn.id!=="runTestBtn")}

function renderNav(){
  document.getElementById("nav").innerHTML=tabs.map(t=>`<button class="${state.tab===t.key?"active":""}" onclick="switchTab('${t.key}')"><span class="nav-ico">${t.icon}</span><span>${t.name}</span></button>`).join("");
  const active=tabs.find(t=>t.key===state.tab)||tabs[0];
  document.getElementById("pageTitle").textContent=active.name;
  document.getElementById("pageSub").textContent=active.sub;
  for(const t of tabs)document.getElementById("tab-"+t.key).style.display=state.tab===t.key?"block":"none";
}
function switchTab(tab){state.tab=tab;renderNav();if(tab==="logs")loadLogs();if(tab==="system")renderSystem()}

function renderMetrics(){
  const account=state.accounts[0]||{};
  const logged=state.accounts.filter(a=>a.runtime?.ready).length;
  const hot=state.accounts.filter(a=>a.runtime?.hot).length;
  const values=[
    ["账号总数",state.accounts.length||1,"LongCat 默认账号池"],
    ["已登录",logged,account.runtime?.ready?"Provider ready":"等待扫码或 Cookie"],
    ["浏览器",hot,account.runtime?.page_url||state.system.browser_data||"--"],
    ["模型数",state.models.length||3,"image / video"]
  ];
  document.getElementById("metrics").innerHTML=values.map(v=>`<div class="card metric"><div class="metric-label">${v[0]}</div><div class="metric-value">${v[1]}</div><div class="metric-meta">${esc(v[2])}</div></div>`).join("");
}
function renderAccounts(){
  const box=document.getElementById("accountList");
  if(!state.accounts.length){box.innerHTML='<div class="empty">暂无账号数据</div>';return}
  box.innerHTML=state.accounts.map(a=>`
    <div class="account-card ${state.selectedId===a.id?"active":""}" onclick="selectAccount('${esc(a.id)}')">
      <div class="account-head">
        <div><div class="account-name">${esc(a.name)}</div><div class="account-id mono">${esc(a.id)}</div></div>
        ${statusBadge(a)}
      </div>
      <div class="badges">
        <span class="badge hot">${a.enabled?"启用":"停用"}</span>
        <span class="badge ${a.runtime?.hot?"ready":"warn"}">${a.runtime?.hot?"browser hot":"browser cold"}</span>
        <span class="badge ${a.runtime?.ready?"ready":"warn"}">${a.runtime?.ready?"login ok":"login required"}</span>
      </div>
      <div class="quota-row">
        <div class="quota-pill"><strong>图片 --</strong><small>LongCat Web 未公开配额接口</small></div>
        <div class="quota-pill"><strong>视频 --</strong><small>以实际生成返回为准</small></div>
      </div>
      <div class="hint mono">${esc(a.runtime?.page_url||a.session_file||"")}</div>
    </div>`).join("");
}
function selectAccount(id){state.selectedId=id;renderAccounts();renderAccountDetail()}
function selectedAccount(){return state.accounts.find(a=>a.id===state.selectedId)||state.accounts[0]||null}
function renderAccountDetail(){
  const a=selectedAccount();
  const box=document.getElementById("accountDetail");
  if(!a){box.innerHTML='<div class="empty">请选择账号</div>';return}
  box.innerHTML=`
    <div class="actions" style="justify-content:space-between">
      <div><h3>${esc(a.name)}</h3><div class="account-id mono">${esc(a.id)}</div></div>
      ${statusBadge(a)}
    </div>
    <div class="detail-grid">
      <div class="kv"><span>Provider</span><span>${esc(a.provider)}</span></div>
      <div class="kv"><span>Enabled</span><span>${a.enabled?"true":"false"}</span></div>
      <div class="kv"><span>Browser</span><span>${a.runtime?.hot?"running":"stopped"}</span></div>
      <div class="kv"><span>Login</span><span>${a.runtime?.ready?"logged in":"required"}</span></div>
      <div class="kv"><span>Page URL</span><span class="mono">${esc(a.runtime?.page_url||"--")}</span></div>
      <div class="kv"><span>Session File</span><span class="mono">${esc(a.session_file||"--")}</span></div>
    </div>
    <div class="actions">
      <button class="btn primary" onclick="startQr('${esc(a.id)}')">扫码登录</button>
      <button class="btn" onclick="probe('${esc(a.id)}')">测活</button>
      <button class="btn" onclick="restartAccount('${esc(a.id)}')">重启浏览器</button>
      <button class="btn" onclick="loadCookies('${esc(a.id)}')">Cookies</button>
      <button class="btn" onclick="takeScreenshot('${esc(a.id)}')">截图</button>
    </div>
    <pre id="probeOutput" style="margin-top:14px">${esc(JSON.stringify(a.runtime?.login_status||{},null,2))}</pre>`;
}

function renderSystem(){
  const s=state.system;
  document.getElementById("systemInfo").innerHTML=[
    ["Service",s.service],
    ["Listen",s.listen],
    ["API Base",API_BASE+"/v1"],
    ["Data Dir",s.data_root],
    ["Browser Data",s.browser_data],
    ["Session File",s.session_file],
    ["Headless",s.headless],
    ["Python",s.python],
    ["Platform",s.platform]
  ].map(([k,v])=>`<div class="kv"><span>${k}</span><span class="mono">${esc(fmt(v))}</span></div>`).join("");
  document.getElementById("serviceKey").value=state.serviceKey;
  document.getElementById("sideBase").textContent=API_BASE+"/v1";
  document.getElementById("modelBadges").innerHTML=(state.models||[]).map(m=>`<span class="badge ready mono">${esc(m.id)}</span>`).join("");
}
function renderLogs(){
  const box=document.getElementById("logs");
  if(!state.logs.length){box.innerHTML='<div class="empty">暂无请求日志</div>';return}
  box.innerHTML=`<table class="table"><thead><tr><th>时间</th><th>方法</th><th>路径</th><th>状态</th><th>耗时</th><th>错误</th></tr></thead><tbody>${
    state.logs.map(l=>`<tr><td class="mono">${esc(l.time)}</td><td>${esc(l.method)}</td><td class="mono">${esc(l.path)}</td><td>${esc(l.status_code)}</td><td>${esc(l.duration_ms)} ms</td><td>${esc(l.error||"")}</td></tr>`).join("")
  }</tbody></table>`;
}

async function refreshAll(){
  setBusy(true);
  try{
    await Promise.all([loadSystem(),loadAccounts(),loadServiceKey(),loadLogs(false)]);
    renderNav();renderMetrics();renderAccounts();renderAccountDetail();renderSystem();renderLogs();
  }catch(e){toast("刷新失败："+e.message)}
  finally{setBusy(false)}
}
async function loadSystem(){state.system=await api("/admin/api/system");state.models=(await api("/v1/models")).data||[]}
async function loadAccounts(){const data=await api("/admin/api/accounts");state.accounts=data.accounts||[];state.selectedId=data.default_account_id||"default"}
async function loadLogs(show=true){try{state.logs=(await api("/admin/api/logs")).logs||[];renderLogs();if(show)toast("日志已刷新")}catch(e){if(show)toast(e.message)}}
async function loadServiceKey(){state.serviceKey=(await api("/admin/api/service/api-key")).api_key||KEY}

async function saveServiceKey(){
  const value=document.getElementById("serviceKey").value.trim();
  const data=await api("/admin/api/service/api-key",{method:"PUT",body:JSON.stringify({api_key:value})});
  state.serviceKey=data.api_key;toast("密钥已更新");renderSystem();
}
async function copyApiBase(){await navigator.clipboard.writeText(API_BASE+"/v1");toast("已复制 API Base")}
async function restartAccount(id){await api(`/admin/api/accounts/${encodeURIComponent(id)}/restart`,{method:"POST"});toast("浏览器已重启");await refreshAll()}
async function probe(id){
  const out=document.getElementById("probeOutput");
  out.textContent="testing...";
  try{out.textContent=JSON.stringify(await api(`/admin/api/accounts/${encodeURIComponent(id)}/probe`,{method:"POST"}),null,2)}
  catch(e){out.textContent=e.message}
  await loadAccounts();renderAccounts();
}
async function loadCookies(id){
  const data=await api(`/admin/api/accounts/${encodeURIComponent(id)}/cookies`);
  openModal("Cookies",`${data.account_id} / ${data.total} items`,`<pre>${esc(JSON.stringify(data.cookies,null,2))}</pre>`);
}
async function takeScreenshot(id){
  const resp=await fetch(`/admin/api/accounts/${encodeURIComponent(id)}/screenshot?key=${encodeURIComponent(state.serviceKey)}`,{headers:authHeaders(false)});
  if(!resp.ok)throw new Error(await resp.text());
  const blob=await resp.blob();
  const url=URL.createObjectURL(blob);
  openModal("浏览器截图","用于确认 LongCat 当前登录和页面状态",`<img src="${url}" />`);
}
async function startQr(id){
  openModal("扫码登录","使用 LongCat 页面支持的登录方式扫码，扫码后本页会轮询登录态。",'<div class="empty">正在生成二维码截图...</div>');
  try{
    const data=await api(`/admin/api/accounts/${encodeURIComponent(id)}/qr-login`,{method:"POST"});
    document.getElementById("modalBody").innerHTML=`<img src="data:image/png;base64,${data.image_base64}" /><pre style="margin-top:12px">${esc(JSON.stringify(data.status,null,2))}</pre>`;
    pollQr(id);
  }catch(e){document.getElementById("modalBody").innerHTML=`<pre>${esc(e.message)}</pre>`}
}
let qrTimer=null;
function pollQr(id){
  clearInterval(qrTimer);
  qrTimer=setInterval(async()=>{
    try{
      const data=await api(`/admin/api/accounts/${encodeURIComponent(id)}/qr-login`);
      if(data.status==="confirmed"){clearInterval(qrTimer);toast("登录成功");await refreshAll()}
    }catch{}
  },2500);
}
function openCookieModal(){
  openModal("导入 Cookie Header","从 longcat.chat 请求头复制完整 Cookie 字符串，粘贴后会写入浏览器 Profile。",`
    <div class="form">
      <label>Cookie Header
        <textarea id="cookieHeader" placeholder="name=value; name2=value2"></textarea>
      </label>
      <button class="btn primary" onclick="importCookie()">导入并检测</button>
      <pre>只导入 LongCat / 美团登录态相关 Cookie，不要在公共环境暴露该内容。</pre>
    </div>`);
}
async function importCookie(){
  const cookie_header=document.getElementById("cookieHeader").value.trim();
  const data=await api("/admin/api/cookies",{method:"POST",body:JSON.stringify({cookie_header})});
  document.getElementById("modalBody").innerHTML=`<pre>${esc(JSON.stringify(data,null,2))}</pre>`;
  await refreshAll();
}
async function runTest(){
  const btn=document.getElementById("runTestBtn");
  const out=document.getElementById("testOutput");
  const model=document.getElementById("testModel").value;
  const prompt=document.getElementById("testPrompt").value.trim();
  btn.disabled=true;out.textContent="requesting...";
  try{
    const path=model.includes("image")?"/v1/images/generations":"/v1/videos";
    const body=model.includes("image")?{model,prompt,n:1}:{model,prompt,wait:true};
    const data=await api(path,{method:"POST",body:JSON.stringify(body)});
    out.textContent=JSON.stringify(data,null,2);
  }catch(e){out.textContent=e.message}
  finally{btn.disabled=false;loadLogs(false)}
}
function openModal(title,sub,body){document.getElementById("modalTitle").textContent=title;document.getElementById("modalSub").textContent=sub||"";document.getElementById("modalBody").innerHTML=body;document.getElementById("modalMask").classList.add("open")}
function closeModal(){clearInterval(qrTimer);document.getElementById("modalMask").classList.remove("open")}

renderNav();
refreshAll();
</script>
</body>
</html>
"""
