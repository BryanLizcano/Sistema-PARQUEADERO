from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from services import openapi_service

router = APIRouter(tags=["Documentación"])

_DOCS_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>API Docs - Parqueadero POS</title>
<style>
  body { font-family: system-ui, -apple-system, sans-serif; margin: 0; background: #f5f7fa; color: #1f2937; }
  header { background: #0f172a; color: #fff; padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; }
  header h1 { font-size: 18px; margin: 0; }
  header .links a { color: #93c5fd; margin-left: 14px; text-decoration: none; font-size: 13px; }
  main { max-width: 1040px; margin: 20px auto; padding: 0 16px; }
  .toolbar { display: flex; gap: 10px; margin-bottom: 16px; }
  input { flex: 1; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 14px; }
  .endpoint { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 10px; overflow: hidden; }
  .ep-head { padding: 10px 14px; display: flex; align-items: center; gap: 10px; cursor: pointer; }
  .ep-head:hover { background: #f8fafc; }
  .method { font-weight: 700; font-size: 12px; padding: 3px 8px; border-radius: 4px; color: #fff; min-width: 58px; text-align: center; }
  .GET { background: #0284c7; } .POST { background: #16a34a; } .PUT { background: #d97706; }
  .PATCH { background: #7c3aed; } .DELETE { background: #dc2626; }
  .path { font-family: monospace; font-size: 14px; font-weight: 600; }
  .summary { color: #64748b; font-size: 13px; margin-left: auto; }
  .ep-body { display: none; padding: 12px 14px; border-top: 1px solid #e2e8f0; background: #fcfcfd; font-size: 13px; }
  pre { background: #0f172a; color: #e2e8f0; padding: 10px; border-radius: 6px; overflow-x: auto; font-size: 12px; }
  .btn { background: #2563eb; color: #fff; border: 0; padding: 6px 12px; border-radius: 5px; cursor: pointer; font-size: 13px; }
  textarea { width: 100%; min-height: 70px; font-family: monospace; font-size: 12px; box-sizing: border-box; margin: 6px 0; }
</style>
</head>
<body>
<header>
  <h1>Parqueadero POS — OpenAPI</h1>
  <div class="links">
    <a href="/api/openapi.yaml" target="_blank">openapi.yaml</a>
    <a href="/api/openapi.json" target="_blank">openapi.json</a>
  </div>
</header>
<main>
  <div class="toolbar">
    <input id="filter" type="search" placeholder="Filtrar endpoints por ruta o método...">
  </div>
  <div id="list">Cargando especificación OpenAPI...</div>
</main>
<script>
(async function() {
  const list = document.getElementById('list');
  const filter = document.getElementById('filter');
  const res = await fetch('/api/openapi.json');
  const spec = await res.json();
  const items = [];

  for (const [path, methods] of Object.entries(spec.paths || {})) {
    for (const [method, op] of Object.entries(methods)) {
      if (!['get','post','put','patch','delete'].includes(method)) continue;
      items.push({ path, method: method.toUpperCase(), op });
    }
  }

  function render(q) {
    const term = (q || '').toLowerCase();
    list.innerHTML = '';
    items.filter(i => (i.method + ' ' + i.path + ' ' + (i.op.summary || '')).toLowerCase().includes(term))
      .forEach((item, idx) => {
        const card = document.createElement('div');
        card.className = 'endpoint';
        const params = (item.op.parameters || []).map(p => `${p.name} (${p.in})`).join(', ') || 'Ninguno';
        const hasBody = !!item.op.requestBody;
        card.innerHTML = `
          <div class="ep-head" data-idx="${idx}">
            <span class="method ${item.method}">${item.method}</span>
            <span class="path">${item.path}</span>
            <span class="summary">${item.op.summary || ''}</span>
          </div>
          <div class="ep-body">
            <div><strong>Tags:</strong> ${(item.op.tags || []).join(', ') || '-'} | <strong>Parámetros:</strong> ${params}</div>
            ${hasBody ? '<div><strong>Body JSON:</strong><textarea placeholder="{}" class="req-body"></textarea></div>' : ''}
            <div style="margin-top:8px;">
              <input class="req-path" value="${item.path}" style="width:65%;margin-right:6px;">
              <button class="btn try-btn">Probar</button>
            </div>
            <pre class="resp-box" style="display:none;margin-top:8px;"></pre>
          </div>`;
        const head = card.querySelector('.ep-head');
        const body = card.querySelector('.ep-body');
        head.onclick = () => { body.style.display = body.style.display === 'block' ? 'none' : 'block'; };
        card.querySelector('.try-btn').onclick = async () => {
          const target = card.querySelector('.req-path').value;
          const opts = { method: item.method, credentials: 'same-origin', headers: {} };
          const bodyEl = card.querySelector('.req-body');
          if (bodyEl && bodyEl.value.trim()) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = bodyEl.value;
          }
          const r = await fetch(target, opts);
          const ct = r.headers.get('content-type') || '';
          const txt = ct.includes('json') ? JSON.stringify(await r.json(), null, 2) : `[${r.status}] ${ct} (${r.headers.get('content-disposition') || 'body'})`;
          const box = card.querySelector('.resp-box');
          box.style.display = 'block';
          box.textContent = `HTTP ${r.status}\\n` + txt;
        };
        list.appendChild(card);
      });
  }

  filter.oninput = (e) => render(e.target.value);
  render('');
})();
</script>
</body>
</html>"""


@router.get("/api/docs", response_class=HTMLResponse, include_in_schema=False)
def api_docs_ui():
    return HTMLResponse(content=_DOCS_HTML)


@router.get("/api/openapi.yaml", include_in_schema=False)
def openapi_yaml(request: Request):
    schema = openapi_service.build_openapi_schema(request.app)
    return Response(
        content=openapi_service.to_yaml(schema),
        media_type="application/yaml; charset=utf-8",
    )
