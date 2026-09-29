"""Browser view of records stored in PostgreSQL."""


def render_admin_html() -> str:
    return """<!doctype html>
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ai_logger — логи</title>
<style>
body{font:16px system-ui;background:#111827;color:#f9fafb;max-width:1200px;margin:32px auto;padding:0 20px}
input,select,button{font:inherit;padding:9px;margin:4px;background:#1f2937;color:inherit;border:1px solid #4b5563;border-radius:5px}
button{cursor:pointer}button:hover{background:#374151}label{display:inline-block;margin:8px}
table{border-collapse:collapse;width:100%;margin-top:20px}td,th{padding:10px;border-bottom:1px solid #374151;text-align:left;vertical-align:top}
td.message{min-width:240px;white-space:pre-wrap;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}
#status{color:#fca5a5}a{color:#93c5fd}
</style>
<h1>Логи ai_logger</h1>
<p><a href="/journal">Локальный журнал</a> · <a href="/health">Состояние сервиса</a></p>
<label>Проект <input id="project" placeholder="Все проекты"></label>
<label>Уровень <select id="level"><option value="">Все</option><option>DEBUG</option><option>INFO</option>
<option>WARNING</option><option>ERROR</option><option>CRITICAL</option></select></label>
<label>Количество <select id="limit"><option>100</option><option>250</option><option>500</option></select></label>
<button id="load">Обновить</button><p id="status" role="status"></p>
<table><thead><tr><th>Время</th><th>Проект</th><th>Уровень</th><th>Источник</th><th>Сообщение</th></tr></thead>
<tbody id="records"></tbody></table>
<script>
const el=id=>document.getElementById(id);
async function load(){
  el('status').textContent='Загрузка...';
  const query=new URLSearchParams({limit:el('limit').value});
  if(el('project').value.trim()) query.set('project',el('project').value.trim());
  if(el('level').value) query.set('levels',el('level').value);
  try{
    const response=await fetch('/api/agent/logs?'+query);
    const payload=await response.json();
    if(!response.ok) throw new Error(payload.error||response.statusText);
    el('records').replaceChildren();
    for(const record of payload.records){
      const tr=document.createElement('tr');
      for(const [index,value] of [record.timestamp||'',record.context?.project||'',record.level||'',
        record.logger||'',record.message||''].entries()){
        const td=document.createElement('td');td.textContent=String(value);
        if(index===4) td.className='message';
        tr.append(td);
      }
      const details=document.createElement('details');
      const summary=document.createElement('summary');summary.textContent='Поля';
      const pre=document.createElement('pre');pre.textContent=JSON.stringify(record.context||{},null,2);
      details.append(summary,pre);tr.lastChild.append(details);
      el('records').append(tr);
    }
    el('status').textContent='Записей: '+payload.records.length;
  }catch(error){el('status').textContent='Ошибка: '+error.message}
}
el('load').onclick=load;
load();
</script></html>"""
