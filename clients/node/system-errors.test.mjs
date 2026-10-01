import test from 'node:test';
import assert from 'node:assert/strict';
import { setTimeout as delay } from 'node:timers/promises';
import { createSanitizer } from './sanitize.mjs';
import {
  createSystemErrorRecorder, createPostgresSystemErrorSink, createHttpSystemErrorSink,
  ensureSystemErrorSchema, pruneSystemErrors,
} from './system-errors.mjs';
import { AiLoggerClient } from './ai-logger-client.mjs';

test('HTTP recorder preserves exception stack and selected entity while excluding raw details', async () => {
  let record;
  const client = new AiLoggerClient({ serverUrl: 'https://logger.example/ingest', project: 'demo',
    fetchImpl: async (_url, options) => { record = JSON.parse(options.body); return { ok: true }; } });
  const recorder = createSystemErrorRecorder({ sink: createHttpSystemErrorSink(client) });
  recorder.secret('registered-private-secret');
  try {
    const error = new Error('Missing configuration token=registered-private-secret');
    error.stack = 'Error: Missing configuration token=registered-private-secret\n at start (src/config.js:12:3)';
    recorder.record('startup', 'startup.error', error, {
      diagnostic: { entity: 'executor', file: 'src/config.js', line: 12 },
      prompt: 'private-prompt', password: 'private-password',
    });
    await recorder.flush();
    assert.equal(record.context.entity, 'executor');
    assert.ok(record.exception.stack_trace.includes('src/config.js:12:3'));
    assert.ok(!JSON.stringify(record).includes('private'));
  } finally { await recorder.close(); }
});

test('private diagnostics are sanitized and retained across a storage outage', async () => {
  let offline = true;
  const rows = [];
  const pool = { async query(sql, values) {
    assert.match(sql, /^INSERT INTO ai_logger_system_errors/);
    if (offline) throw new Error('offline');
    rows.push(values);
  } };
  const recorder = createSystemErrorRecorder({ sink: createPostgresSystemErrorSink(pool, 'demo') });
  recorder.secret('private-test-token');
  try {
    recorder.record('server', 'example.error', Object.assign(new Error('Bearer private-test-token'), { code: 'TEST' }), {
      url: 'https://user:password@example.test/path?token=private-test-token#private', password: 'private-test-token',
      response: '{"token":"private-test-token","status":500}', buffer: Buffer.from('private-test-token'),
    });
    await recorder.flush();
    assert.equal(rows.length, 0);
    assert.equal(recorder.status().pending, 1);
    offline = false;
    await recorder.flush();
    assert.equal(rows.length, 1);
    assert.equal(rows[0][0], 'demo');
    assert.equal(rows[0][3], 'TEST');
    assert.ok(!JSON.stringify(rows).includes('private-test-token'));
    const details = JSON.parse(rows[0][5]);
    assert.equal(details.password, '[REDACTED]');
    assert.equal(details.url, 'https://example.test/path');
    assert.equal(details.response.token, '[REDACTED]');
    assert.deepEqual(details.buffer, { bytes: 18 });
  } finally { await recorder.close(); }
});

test('queue overflow preserves the in-flight row and does not discard its successor on completion', async () => {
  const rows = [];
  let release;
  const blocked = new Promise(resolve => { release = resolve; });
  const recorder = createSystemErrorRecorder({ maxPending: 2, sink: async row => {
    if (row.event === 'first') await blocked;
    rows.push(row.event);
  } });
  try {
    recorder.record('test', 'first', 'first');
    await Promise.resolve();
    recorder.record('test', 'second', 'second');
    recorder.record('test', 'third', 'third');
    assert.equal(recorder.status().pending, 2);
    release();
    await recorder.flush();
    assert.deepEqual(rows, ['first', 'third']);
    assert.equal(recorder.status().dropped, 1);
  } finally { release(); await recorder.close(); }
});

test('false delivery result is retried automatically without a new log call', async () => {
  let attempts = 0;
  let delivered;
  const done = new Promise(resolve => { delivered = resolve; });
  const recorder = createSystemErrorRecorder({ retryMs: 5, sink: async () => {
    if (++attempts === 1) return false;
    delivered();
    return true;
  } });
  try {
    recorder.record('test', 'retry', 'failed');
    await recorder.flush();
    await Promise.race([done, delay(500).then(() => { throw new Error('retry did not run'); })]);
    await recorder.flush();
    assert.equal(attempts, 2);
    assert.equal(recorder.status().pending, 0);
  } finally { await recorder.close(); }
});

test('recorders isolate secrets and pending rows; attaching a sink drains existing rows', async () => {
  const a = createSystemErrorRecorder();
  const b = createSystemErrorRecorder();
  const rows = [];
  try {
    a.secret('instance-secret');
    a.record('test', 'a', 'instance-secret');
    b.record('test', 'b', 'instance-secret');
    await a.setSink(async row => rows.push(row.message));
    await b.setSink(async row => rows.push(row.message));
    assert.deepEqual(rows, ['[REDACTED]', 'instance-secret']);
  } finally { await a.close(); await b.close(); }
});

test('sanitizer bounds cyclic errors, nested data and binary payloads', () => {
  const sanitizer = createSanitizer();
  const error = new Error('failed'); error.cause = error;
  const cleaned = sanitizer.clean({ error, code: 'token=secret', binary: new Uint8Array(7) });
  assert.doesNotThrow(() => JSON.stringify(cleaned));
  assert.ok(JSON.stringify(cleaned).includes('[DEPTH LIMIT]'));
  assert.equal(cleaned.code, 'token=[REDACTED]');
  assert.deepEqual(cleaned.binary, { bytes: 7 });
});

test('HTTP transport forwards error diagnostics while excluding arbitrary private details', async () => {
  let captured;
  const client = new AiLoggerClient({ serverUrl: 'https://logger.example/ingest', project: 'demo',
    fetchImpl: async (_url, options) => { captured = JSON.parse(options.body); return { ok: true }; },
  });
  const recorder = createSystemErrorRecorder({ sink: createHttpSystemErrorSink(client) });
  try {
    recorder.record('worker', 'provider.failed', Object.assign(new Error('Provider timed out'), { code: 'TIMEOUT' }),
      { prompt: 'private prompt', accountId: 'private account' });
    await recorder.flush();
    assert.equal(captured.message, 'provider.failed');
    assert.equal(captured.context.error_code, 'TIMEOUT');
    assert.equal(captured.context.project, 'demo');
    assert.equal(captured.exception.message, 'Provider timed out');
    assert.ok(!JSON.stringify(captured).includes('private'));
  } finally { await recorder.close(); }
});

test('schema installation is explicit and retention is project-scoped and bounded', async () => {
  const queries = [];
  const pool = { async query(sql, values) { queries.push({ sql, values }); return { rowCount: 1 }; } };
  await ensureSystemErrorSchema(pool);
  assert.match(queries[0].sql, /CREATE TABLE IF NOT EXISTS ai_logger_system_errors/);
  assert.equal(await pruneSystemErrors(pool, 'demo', 90, 1), 1);
  assert.match(queries[1].sql, /WHERE project=\$1/);
  assert.match(queries[1].sql, /LIMIT \$3/);
  assert.deepEqual(queries[1].values, ['demo', 90, 1]);
  await assert.rejects(pruneSystemErrors(pool, '', 90, 1), /project/);
  await assert.rejects(pruneSystemErrors(pool, 'demo', -1, 1), /positive/);
});

test('console capture preserves output and restores the original handler', async () => {
  const output = [], rows = [];
  const target = { error: (...args) => output.push(args) };
  const original = target.error;
  const recorder = createSystemErrorRecorder({ sink: async row => rows.push(row) });
  const restore = recorder.captureConsole(target);
  try {
    target.error('worker failed', new Error('failed'));
    await recorder.flush();
    assert.equal(output.length, 1);
    assert.equal(rows[0].event, 'console.error');
    assert.equal(rows[0].message, 'failed');
  } finally { restore(); await recorder.close(); }
  assert.equal(target.error, original);
});

test('background retention retries failures and close stops further work', async () => {
  let calls = 0, pruned;
  const done = new Promise(resolve => { pruned = resolve; });
  const pool = { async query() {
    if (++calls === 1) throw new Error('offline');
    pruned(); return { rowCount: 0 };
  } };
  const recorder = createSystemErrorRecorder();
  recorder.startRetention(pool, 'demo', { initialDelayMs: 1, failureDelayMs: 1, intervalMs: 1000 });
  try {
    await Promise.race([done, delay(500).then(() => { throw new Error('retention did not retry'); })]);
  } finally { await recorder.close(); }
  await delay(10);
  assert.equal(calls, 2);
  assert.equal(recorder.record('test', 'after.close', 'ignored'), false);
});
