import test from 'node:test';
import assert from 'node:assert/strict';
import { AiLoggerClient } from './ai-logger-client.mjs';

test('sends a normalized, restricted record without a key', async () => {
  let captured;
  const client = new AiLoggerClient({
    serverUrl: 'https://logger.example/ingest', project: 'ai-media-client',
    fetchImpl: async (_url, options) => { captured = options; return { ok: true }; },
  });
  assert.equal(await client.send({
    message: 'provider.failed', context: { error_code: 'UPSTREAM', prompt: 'private prompt', token: 'private token' },
  }), true);
  const record = JSON.parse(captured.body);
  assert.equal(captured.headers.Authorization, undefined);
  assert.equal(record.context.project, 'ai-media-client');
  assert.equal(record.context.instance_id, undefined);
  assert.equal(record.context.error_code, 'UPSTREAM');
  assert.equal(record.context.prompt, undefined);
  assert.equal(record.context.token, undefined);
});

test('returns false when server is unavailable', async () => {
  const client = new AiLoggerClient({
    serverUrl: 'https://logger.example/ingest', project: 'demo',
    fetchImpl: async () => { throw new Error('offline'); },
  });
  assert.equal(await client.send({ message: 'event.failed' }), false);
});

test('sends bounded error diagnostics while redacting credentials and excluding raw payloads', async () => {
  let record;
  const client = new AiLoggerClient({
    serverUrl: 'https://logger.example/ingest', project: 'demo',
    fetchImpl: async (_url, options) => { record = JSON.parse(options.body); return { ok: true }; },
  });
  await client.send({
    message: 'startup.error',
    context: { description: 'Configuration is invalid', file: 'src/start.js', line: 42,
      function: 'start', entity: 'executor', prompt: 'private prompt' },
    exception: { name: 'TypeError', message: 'token=private-token',
      stack: 'TypeError: Bearer private-bearer\n at start (src/start.js:42:3)\n'+
        'https://user:pass@example.test/path?token=private-url#private\n'+'x'.repeat(6000),
      payload: 'private payload' },
  });
  assert.equal(record.context.line, '42');
  assert.equal(record.context.description, 'Configuration is invalid');
  assert.equal(record.exception.type, 'TypeError');
  assert.ok(record.exception.stack_trace.includes('src/start.js:42:3'));
  assert.ok(record.exception.stack_trace.length <= 4000);
  assert.ok(!JSON.stringify(record).includes('private'));
});

test('machine identity persists across clients and cannot be overridden by an event', async () => {
  const records = [];
  const env = { AI_LOGGER_SERVER_URL: 'https://logger.example/ingest', AI_LOGGER_PROJECT: 'demo',
    AI_LOGGER_SERVICE: 'executor', AI_LOGGER_ENVIRONMENT: 'local', AI_LOGGER_INSTANCE_ID: ' my-pc ' };
  for (let restart = 0; restart < 2; restart++) {
    const client = AiLoggerClient.fromEnv(env);
    client.fetchImpl = async (_url, options) => {
      records.push(JSON.parse(options.body)); return { ok: true };
    };
    await client.send({ message: 'machine.check', context: { instance_id: 'container-id' } });
  }
  assert.deepEqual(records.map(record => record.context.instance_id), ['my-pc', 'my-pc']);
  assert.equal(records[0].context.service, 'executor');
  assert.equal(records[0].context.environment, 'local');
  assert.notEqual(records[0].id, records[1].id);
});

test('requires HTTPS for remote log delivery', () => {
  assert.throws(() => new AiLoggerClient({
    serverUrl: 'http://logger.example/ingest', project: 'demo',
  }), /HTTPS is required/);
  assert.throws(() => new AiLoggerClient({
    serverUrl: 'http://logger.example/ingest', project: 'demo', allowPrivateHttp: true,
  }), /HTTPS is required/);
  assert.doesNotThrow(() => new AiLoggerClient({
    serverUrl: 'http://192.168.3.63:8765/ingest', project: 'demo', allowPrivateHttp: true,
  }));
});
