"""Small browser console for issuing scoped client and agent API keys."""


def render_admin_html() -> str:
    return """<!doctype html>
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ai_logger — ключи</title>
<style>
body{font:16px system-ui;background:#111827;color:#f9fafb;max-width:850px;margin:40px auto;padding:0 20px}
input,button{font:inherit;padding:9px;margin:4px;background:#1f2937;color:inherit;border:1px solid #4b5563;border-radius:5px}
button{cursor:pointer}button:hover{background:#374151}label{display:inline-block;margin:8px}
table{border-collapse:collapse;width:100%;margin-top:20px}td,th{padding:10px;border-bottom:1px solid #374151;text-align:left}
code{word-break:break-all}#issued{background:#064e3b;padding:14px;display:none}#status{color:#fca5a5}
</style>
<h1>Ключи ai_logger</h1><p>Токен администратора задаётся через <code>AI_LOGGER_ADMIN_TOKEN</code>.</p>
<label>Токен администратора <input id="adminToken" type="password" autocomplete="off"></label>
<button id="load">Загрузить ключи</button><p id="status" role="alert"></p>
<h2>Новый ключ</h2>
<label>Название <input id="name" placeholder="media-client"></label>
<label>Проект <input id="project" placeholder="ai-media-client"></label><br>
<label><input id="ingest" type="checkbox">Отправка логов</label>
<label><input id="read" type="checkbox">Чтение агентом</label>
<button id="create">Создать</button>
<p id="issued">Скопируйте сейчас: <code id="newKey"></code>. После закрытия страницы значение нельзя получить снова.</p>
<table><thead><tr><th>Название</th><th>Префикс</th><th>Права</th><th>Проект</th><th>Статус</th><th></th></tr></thead><tbody id="keys"></tbody></table>
<p><a href="/" style="color:#93c5fd">Просмотр логов</a></p>
<script>
const el=id=>document.getElementById(id);
async function api(path, options={}) {
 const token=el('adminToken').value.trim();
 const response=await fetch(path,{...options,headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'}});
 const payload=await response.json();
 if(!response.ok) throw new Error(payload.error||response.statusText);
 return payload;
}
async function load(){
 try {
  el('status').textContent=''; const result=await api('/api/admin/keys'); el('keys').replaceChildren();
  for(const key of result.keys){
   const tr=document.createElement('tr');
   for(const value of [key.name,key.key_prefix,key.scopes.join(', '),key.project||'Все',key.revoked_at?'Отозван':'Активен']){
    const td=document.createElement('td'); td.textContent=value; tr.append(td);
   }
   const td=document.createElement('td');
   if(!key.revoked_at){const button=document.createElement('button');button.textContent='Отозвать';
    button.onclick=async()=>{if(confirm('Отозвать ключ?')){try{await api('/api/admin/keys/'+key.id,{method:'DELETE'});await load()}catch(e){el('status').textContent=e.message}}};td.append(button)}
   tr.append(td);el('keys').append(tr);
  }
 }catch(e){el('status').textContent=e.message}
}
el('load').onclick=load;
el('create').onclick=async()=>{
 try{
  el('status').textContent='';
  const scopes=['ingest','read'].filter(scope=>el(scope).checked);
  const result=await api('/api/admin/keys',{method:'POST',body:JSON.stringify({name:el('name').value,project:el('project').value||null,scopes})});
  el('newKey').textContent=result.key;el('issued').style.display='block';await load();
 }catch(e){el('status').textContent=e.message}
};
</script></html>"""
