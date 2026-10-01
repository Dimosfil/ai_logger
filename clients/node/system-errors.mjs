import { readFile } from 'node:fs/promises';
import { createSanitizer } from './sanitize.mjs';

function positiveInteger(value, name) {
  if (!Number.isSafeInteger(value) || value < 1) throw new TypeError(`${name} must be a positive integer`);
  return value;
}

/** Explicit schema installation; importing or constructing a recorder never touches the DB. */
export async function ensureSystemErrorSchema(pool) {
  const sql = await readFile(new URL('./system-errors.sql', import.meta.url), 'utf8');
  await pool.query(sql);
}

/** Bounded project-specific retention. Consumers never delete another project's errors. */
export async function pruneSystemErrors(pool, project, days = 90, limit = 500) {
  if (typeof project !== 'string' || !project.trim()) throw new TypeError('project is required');
  positiveInteger(days, 'days'); positiveInteger(limit, 'limit');
  const result = await pool.query(`DELETE FROM ai_logger_system_errors WHERE id IN (
    SELECT id FROM ai_logger_system_errors WHERE project=$1
    AND occurred_at < now()-($2::int * interval '1 day')
    ORDER BY occurred_at,id LIMIT $3)`, [project, days, limit]);
  return result.rowCount || 0;
}

/** Preserve private diagnostics in a supplied logger-owned PostgreSQL pool. */
export function createPostgresSystemErrorSink(pool, project) {
  if (typeof project !== 'string' || !project.trim()) throw new TypeError('project is required');
  return row => pool.query(
    'INSERT INTO ai_logger_system_errors(project,source,event,code,message,details) VALUES($1,$2,$3,$4,$5,$6)',
    [project, row.source, row.event, row.code, row.message, JSON.stringify(row.details)],
  );
}

/** Send selected diagnostics; arbitrary private messages/details remain local. */
export function createHttpSystemErrorSink(client) {
  const identifier = (value, fallback) => /^[A-Za-z0-9_.:-]{1,150}$/.test(String(value ?? ''))
    ? String(value) : fallback;
  return row => client.send({
    level: 'ERROR', logger: `${client.project}.${identifier(row.source, 'system')}`,
    message: identifier(row.event, 'system.error'),
    context: { source: identifier(row.source, 'system'), error_code: identifier(row.code, 'unknown'),
      ...Object.fromEntries(['description', 'file', 'line', 'function', 'entity']
        .filter(key => row.diagnostic?.[key] != null).map(key => [key, row.diagnostic[key]])) },
    exception: row.exception || row.diagnostic?.exception,
  });
}

/** Instance-owned state replaces media-client globals. sink(row) rejects/returns false on failure. */
export function createSystemErrorRecorder({
  sink = null, sanitizer = createSanitizer(), maxPending = 500, retryMs = 5000,
} = {}) {
  positiveInteger(maxPending, 'maxPending'); positiveInteger(retryMs, 'retryMs');
  if (sink !== null && typeof sink !== 'function') throw new TypeError('sink must be a function');
  let pending = [], draining = null, retryTimer = null, closed = false, dropped = 0;
  let retentionTimer = null, retentionGeneration = 0;
  const retentionTasks = new Set();
  let inFlight = null;
  const cancelRetry = () => { clearTimeout(retryTimer); retryTimer = null; };

  function normalize(source, event, error, details = {}) {
    const safe = sanitizer.clean({ error, details });
    const value = safe.error;
    const message = typeof value === 'string' ? value : value?.message || String(value ?? event);
    return {
      source: String(sanitizer.clean(String(source))).slice(0, 100),
      event: String(sanitizer.clean(String(event))).slice(0, 150),
      code: value?.code == null ? null : String(value.code).slice(0, 100),
      message: String(message).slice(0, 4000), details: safe.details || {},
      diagnostic: safe.details?.diagnostic,
      exception: error instanceof Error ? {
        type: value?.name || 'Error', message: String(message).slice(0, 1000),
        stack_trace: String(value?.stack || '').slice(0, 4000),
      } : undefined,
    };
  }

  function record(source, event, error, details) {
    if (closed) return false;
    try {
      const row = normalize(source, event, error, details);
      if (pending.length >= maxPending) {
        const index = pending[0] === inFlight ? 1 : 0;
        dropped++;
        if (index >= pending.length) return false;
        pending.splice(index, 1);
      }
      pending.push(row);
      void flush();
      return true;
    } catch { return false; } // Logging must never interrupt the original operation.
  }

  function flush() {
    if (closed || !sink || !pending.length) return draining || Promise.resolve();
    if (draining) return draining;
    cancelRetry();
    draining = Promise.resolve().then(async () => {
      while (!closed && sink && pending.length) {
        const row = pending[0];
        inFlight = row;
        try {
          if (await sink(row) === false) throw new Error('delivery failed');
          pending.shift();
        } catch {
          if (!closed) {
            retryTimer = setTimeout(() => { retryTimer = null; void flush(); }, retryMs);
            retryTimer.unref?.();
          }
          break;
        } finally { inFlight = null; }
      }
    }).finally(() => { draining = null; });
    return draining;
  }

  function setSink(nextSink) {
    if (closed) throw new Error('recorder is closed');
    if (nextSink !== null && typeof nextSink !== 'function') throw new TypeError('sink must be a function');
    sink = nextSink;
    cancelRetry();
    return flush();
  }

  function stopRetention() {
    retentionGeneration++;
    clearTimeout(retentionTimer); retentionTimer = null;
  }

  function startRetention(pool, project, {
    days = 90, limit = 500, initialDelayMs = 30000, intervalMs = 3600000,
    batchDelayMs = 1000, failureDelayMs = 300000,
  } = {}) {
    if (closed) throw new Error('recorder is closed');
    if (typeof project !== 'string' || !project.trim()) throw new TypeError('project is required');
    for (const [name, value] of Object.entries({ days, limit, initialDelayMs, intervalMs, batchDelayMs, failureDelayMs })) {
      positiveInteger(value, name);
    }
    stopRetention();
    const generation = retentionGeneration;
    function schedule(delay) {
      retentionTimer = setTimeout(() => {
        retentionTimer = null;
        const task = (async () => {
          let nextDelay = intervalMs;
          try { if (await pruneSystemErrors(pool, project, days, limit) === limit) nextDelay = batchDelayMs; }
          catch { nextDelay = failureDelayMs; }
          if (!closed && generation === retentionGeneration) schedule(nextDelay);
        })();
        retentionTasks.add(task);
        void task.finally(() => { retentionTasks.delete(task); });
      }, delay);
      retentionTimer.unref?.();
    }
    schedule(initialDelayMs);
  }

  function captureConsole(target = console) {
    const original = target.error;
    function captured(...args) {
      original.apply(target, args);
      const [first, ...rest] = args;
      const error = rest.find(value => value instanceof Error) || (first instanceof Error ? first : rest.at(-1));
      record('server', 'console.error', error || first, { context: first instanceof Error ? undefined : first });
    }
    target.error = captured;
    return () => { if (target.error === captured) target.error = original; };
  }

  async function close() {
    closed = true;
    cancelRetry(); stopRetention();
    await draining;
    await Promise.all(retentionTasks);
    return { pending: pending.length, dropped };
  }

  return {
    record, flush, setSink, captureConsole, startRetention, stopRetention, close,
    secret: sanitizer.secret,
    status: () => ({ pending: pending.length, dropped, closed }),
  };
}
