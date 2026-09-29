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

test('requires HTTPS for remote log delivery', () => {
  assert.throws(() => new AiLoggerClient({
    serverUrl: 'http://logger.example/ingest', project: 'demo',
  }), /HTTPS is required/);
});
