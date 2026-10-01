"""Browser view of records stored in PostgreSQL."""


def render_admin_html() -> str:
    return """<!doctype html>
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ai_logger — логи</title>
<style>
body{font:16px system-ui;background:#111827;color:#f9fafb;max-width:1200px;margin:32px auto;padding:0 20px}
input,select,button{font:inherit;padding:9px;margin:4px;background:#1f2937;color:inherit;border:1px solid #4b5563;border-radius:5px}
button{cursor:pointer}button:hover{background:#374151}label{display:inline-block;margin:8px}
.level-filter{display:inline-block;vertical-align:middle;border:1px solid #4b5563;border-radius:5px;margin:8px;padding:4px 8px}
.level-filter label{margin:4px;white-space:nowrap}.level-filter input{accent-color:#2563eb;padding:0}
table{border-collapse:collapse;width:100%;margin-top:20px}td,th{padding:10px;border-bottom:1px solid #374151;text-align:left;vertical-align:top}
td.message{min-width:240px;white-space:pre-wrap;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}
td.time{white-space:nowrap;font-variant-numeric:tabular-nums}
.event,.hint{color:#9ca3af;font-size:13px;margin-top:6px}.diagnostic{margin-top:8px}
dl{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:14px}dt{color:#9ca3af}dd{margin:0;overflow-wrap:anywhere}
details{margin-top:8px}summary{cursor:pointer}pre.stack{font-size:12px;padding:8px;background:#1f2937;border-radius:5px}
#status{color:#fca5a5}a{color:#93c5fd}
</style>
<h1>Логи ai_logger</h1>
<p><a href="/journal">Локальный журнал</a> · <a href="/health">Состояние сервиса</a></p>
<label>Проект <input id="project" placeholder="Все проекты"></label>
<fieldset id="levels" class="level-filter"><legend>Уровни</legend>
<label><input id="all-levels" type="checkbox" checked>Все</label>
<label><input type="checkbox" name="level" value="DEBUG">DEBUG</label>
<label><input type="checkbox" name="level" value="INFO">INFO</label>
<label><input type="checkbox" name="level" value="WARNING">WARNING</label>
<label><input type="checkbox" name="level" value="ERROR">ERROR</label>
<label><input type="checkbox" name="level" value="CRITICAL">CRITICAL</label>
</fieldset>
<label>Количество <select id="limit"><option>100</option><option>250</option><option>500</option></select></label>
<button id="load">Обновить</button><p id="status" role="status"></p>
<table><thead><tr><th>Время</th><th>Проект</th><th>Машина</th><th>Уровень</th><th>Источник</th><th>Сообщение</th></tr></thead>
<tbody id="records"></tbody></table>
<script>
const el=id=>document.getElementById(id);
function formatTimestamp(value){
  if(!value) return '—';
  const date=new Date(value);
  if(Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString('ru-RU')+' '+date.toLocaleTimeString('ru-RU',
    {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
}
function renderDiagnostic(cell,record){
  cell.replaceChildren();
  const context=record.context||{},exception=record.exception||{};
  const eventNames={
    'startup.error':'Ошибка запуска приложения',
    'runtime.error':'Ошибка во время работы приложения',
    'config.error':'Ошибка конфигурации',
    'console.error':'Ошибка, записанная в консоль',
    'system.error':'Системная ошибка',
    'request.failed':'Не удалось выполнить запрос',
    'provider.request_failed':'Не удалось выполнить запрос к провайдеру',
  };
  const codeNames={CONFIG_INVALID:'Некорректная конфигурация',UPSTREAM_TIMEOUT:'Истекло время ожидания внешнего сервиса'};
  const text=(parent,tag,value,className)=>{
    const element=document.createElement(tag);element.textContent=String(value);
    if(className) element.className=className;
    parent.append(element);return element;
  };
  const description=context.description||exception.message;
  text(cell,'div',description||eventNames[record.message]||record.message||'Сообщение отсутствует');
  if(description||eventNames[record.message]) text(cell,'div','Событие: '+record.message,'event');
  if(context.error_code) text(cell,'div','Код: '+context.error_code+
    (codeNames[context.error_code]?' — '+codeNames[context.error_code]:''),'diagnostic');
  const location=context.file||context.module;
  if(location) text(cell,'div','Место: '+location+
    (context.line?':'+context.line:'')+(context.function?' · '+context.function:''),'diagnostic');
  if(context.entity) text(cell,'div','Сущность: '+context.entity,'diagnostic');
  if(exception.type) text(cell,'div','Тип: '+exception.type,'diagnostic');
  const stack=typeof exception.stack_trace==='string'?exception.stack_trace.trim():'';
  if(stack){
    const lines=stack.split(/\\r?\\n/);
    const short=stack.startsWith('Traceback')?lines.slice(-8):lines.slice(0,8);
    text(cell,'div','Стек вызовов'+(lines.length>8?' (фрагмент)':''),'diagnostic');
    text(cell,'pre',short.join('\\n'),'stack');
  }else if(['ERROR','CRITICAL'].includes(record.level)){
    text(cell,'div',description?'Стек вызовов не передан приложением.':
      'Подробная причина и стек вызовов не переданы приложением.','hint');
  }
  const labels={service:'Роль',environment:'Окружение',source:'Компонент',component:'Компонент',
    operation:'Операция',request_id:'ID запроса',trace_id:'ID трассировки',job_id:'ID задачи',
    provider:'Провайдер',status:'Статус',host:'Хост',thread:'Поток',process:'Процесс',
    function:'Функция',line:'Строка'};
  const items=Object.entries(context).filter(([key,value])=>labels[key]&&
    value!==null&&value!==''&&['string','number','boolean'].includes(typeof value));
  if(items.length){
    const details=document.createElement('details');
    text(details,'summary','Подробности');
    const list=document.createElement('dl');
    for(const [key,value] of items){text(list,'dt',labels[key]);text(list,'dd',value);}
    details.append(list);cell.append(details);
  }
}
async function load(){
  el('status').textContent='Загрузка...';
  const query=new URLSearchParams({limit:el('limit').value});
  if(el('project').value.trim()) query.set('project',el('project').value.trim());
  const levels=Array.from(document.querySelectorAll('input[name="level"]:checked'),input=>input.value);
  if(levels.length) query.set('levels',levels.join(','));
  try{
    const response=await fetch('/api/agent/logs?'+query);
    const payload=await response.json();
    if(!response.ok) throw new Error(payload.error||response.statusText);
    el('records').replaceChildren();
    for(const record of payload.records){
      const tr=document.createElement('tr');
      for(const [index,value] of [formatTimestamp(record.timestamp),record.context?.project||'',
        record.context?.instance_id||'—',record.level||'',
        record.logger||'',record.message||''].entries()){
        const td=document.createElement('td');td.textContent=String(value);
        if(index===0){td.className='time';td.title=record.timestamp||'';}
        if(index===5) td.className='message';
        tr.append(td);
      }
      renderDiagnostic(tr.lastChild,record);
      el('records').append(tr);
    }
    el('status').textContent='Записей: '+payload.records.length;
  }catch(error){el('status').textContent='Ошибка: '+error.message}
}
el('load').onclick=load;
el('levels').onchange=event=>{
  const inputs=Array.from(document.querySelectorAll('input[name="level"]'));
  if(event.target.id==='all-levels') inputs.forEach(input=>{input.checked=false;});
  el('all-levels').checked=!inputs.some(input=>input.checked);
  load();
};
load();
</script></html>"""
