const lifecycleEvents = new Set([
  'session.start', 'queue.start', 'queue.pause', 'queue.close',
  'task.enqueued', 'task.status', 'task.cost',
]);

function safeIdentifier(value, fallback) {
  const text = String(value ?? '');
  return /^[A-Za-z0-9_.:-]{1,150}$/.test(text) ? text : fallback;
}

function createForwarder({ env = process.env, fetchImpl = fetch } = {}) {
  if (!env.AI_LOGGER_SERVER_URL) return null;
  const makeClient = () => import('./ai-logger-client.mjs').then(({ AiLoggerClient }) => new AiLoggerClient({
    serverUrl: env.AI_LOGGER_SERVER_URL,
    project: 'ai-media-client',
    service: env.AI_LOGGER_SERVICE || env.MEDIA_REPLICA_ROLE || 'web',
    environment: env.AI_LOGGER_ENVIRONMENT || 'production',
    fallbackJsonlPath: env.AI_LOGGER_FALLBACK_JSONL_PATH || null,
    timeoutMs: 1500,
    fetchImpl,
  }));
  const pending = [];
  let draining = null;
  let disabled = false;

  function drain() {
    if (draining) return draining;
    draining = (async () => {
      let client;
      try { client = await makeClient(); }
      catch {
        pending.length = 0;
        disabled = true;
        console.warn('ai_logger: проверьте AI_LOGGER_SERVER_URL');
        return;
      }
      while (pending.length) await client.send(pending.shift());
    })().finally(() => { draining = null; if (pending.length) void drain(); });
    return draining;
  }

  function enqueue(record) {
    if (disabled) return;
    if (pending.length >= 100) pending.shift();
    pending.push(record);
    void drain();
  }

  return {
    lifecycle(event) {
      if (!lifecycleEvents.has(event)) return;
      enqueue({ level: 'INFO', logger: 'ai-media-client.generation', message: event });
    },
    systemError(row) {
      const source = safeIdentifier(row.source, 'system');
      const code = safeIdentifier(row.code, 'unknown');
      enqueue({
        level: 'ERROR', logger: `ai-media-client.${source}`,
        message: safeIdentifier(row.event, 'system.error'),
        context: { source, error_code: code },
      });
    },
    async flush() { while (draining || pending.length) await (draining || drain()); },
  };
}

const forwarder = createForwarder();
function reportLifecycle(event) { forwarder?.lifecycle(event); }
function reportSystemError(row) { forwarder?.systemError(row); }
async function flush() { await forwarder?.flush(); }

module.exports = { createForwarder, reportLifecycle, reportSystemError, flush };
