from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ai_logger.admin import render_admin_html


@unittest.skipUnless(shutil.which("node"), "Node.js is required for admin JavaScript checks")
class AdminUiTests(unittest.TestCase):
    def test_rendered_script_displays_diagnostics_and_handles_old_records_safely(self):
        harness = r"""
const vm = require('node:vm'), assert = require('node:assert/strict');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', data => input += data);
process.stdin.on('end', () => {
  class Element {
    constructor() { this.children = []; this.textContent = ''; this.value = ''; }
    append(...items) { this.children.push(...items); }
    replaceChildren() { this.children = []; this.textContent = ''; }
    set innerHTML(value) { throw new Error('Unsafe HTML rendering'); }
  }
  const elements = {};
  const context = vm.createContext({
    document: { getElementById: id => elements[id] ||= new Element(),
      createElement: () => new Element() },
    URLSearchParams, fetch: async () => ({ok:true,json:async()=>({records:[]})}),
  });
  const html = JSON.parse(input);
  vm.runInContext(html.split('<script>')[1].split('</script>')[0], context);
  const flatten = element => [element.textContent, ...element.children.map(flatten)].join('\n');
  const render = record => {
    context.cell = new Element(); context.record = record;
    vm.runInContext('renderDiagnostic(cell,record)', context);
    return { cell: context.cell, text: flatten(context.cell) };
  };
  const legacy = render({level:'ERROR',message:'startup.error',context:{
    error_code:'CONFIG_INVALID',service:'executor',environment:'local',payload:{private:'hidden'}}});
  assert.ok(legacy.text.includes('Ошибка запуска приложения'));
  assert.ok(legacy.text.includes('Некорректная конфигурация'));
  assert.ok(legacy.text.includes('не переданы приложением'));
  assert.ok(legacy.text.includes('Роль'));
  assert.ok(!legacy.text.includes('hidden'));
  const detailed = render({level:'ERROR',message:'request.failed',context:{
    description:'<script>alert(1)</script>',file:'src/config.js',line:12,entity:'worker',
  },exception:{type:'TypeError',message:'failed',stack_trace:
    Array.from({length:20},(_,i)=>' at f'+i+' (config.js:'+i+':1)').join('\n')}});
  assert.ok(detailed.text.includes('src/config.js:12'));
  assert.ok(detailed.text.includes('Сущность: worker'));
  assert.ok(detailed.text.includes('<script>alert(1)</script>'));
  assert.ok(detailed.text.includes('Стек вызовов (фрагмент)'));
  const stack = detailed.cell.children.find(child=>child.className==='stack');
  assert.equal(stack.textContent.split('\n').length,8);
  assert.ok(!render({level:'INFO',message:'session.start'}).text.includes('не переданы'));
  console.log('Admin diagnostic rendering passed');
});
"""
        result = subprocess.run(
            [shutil.which("node"), "-e", harness],
            input=json.dumps(render_admin_html()), text=True, encoding="utf-8",
            capture_output=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
