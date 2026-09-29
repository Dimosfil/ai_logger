const test = require('node:test');
const assert = require('node:assert/strict');
const { createForwarder } = require('../src/ai-logger');

test('central logger forwards only selected diagnostic metadata', async () => {
  const records = [];
  const forwarder = createForwarder({
    env: {
      AI_LOGGER_SERVER_URL: 'http://127.0.0.1:8766/ingest',
      MEDIA_REPLICA_ROLE: 'executor',
    },
    fetchImpl: async (_url, options) => {
      records.push(JSON.parse(options.body));
      return { ok: true };
    },
  });
  forwarder.lifecycle('http.body');
  forwarder.lifecycle('task.enqueued');
  forwarder.systemError({
    source: 'provider', event: 'request.failed', code: 'UPSTREAM_TIMEOUT',
    message: 'private prompt', details: { token: 'private key', accountId: 'private account' },
  });
  await forwarder.flush();
  assert.equal(records.length, 2);
  assert.equal(records[0].message, 'task.enqueued');
  assert.equal(records[1].message, 'request.failed');
  assert.equal(records[1].level, 'ERROR');
  assert.equal(records[1].context.project, 'ai-media-client');
  assert.equal(records[1].context.service, 'executor');
  assert.equal(records[1].context.error_code, 'UPSTREAM_TIMEOUT');
  assert.ok(!JSON.stringify(records).includes('private'));
});

test('central logger leaves application flow unaffected when delivery fails', async () => {
  const forwarder = createForwarder({
    env: { AI_LOGGER_SERVER_URL: 'http://127.0.0.1:8766/ingest' },
    fetchImpl: async () => { throw new Error('offline'); },
  });
  forwarder.systemError({ source: 'server', event: 'startup.error' });
  await forwarder.flush();
});
