import { appendFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';
import { randomUUID } from 'node:crypto';

const LEVELS = new Set(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']);
const CONTEXT_FIELDS = new Set([
  'component', 'operation', 'error_code', 'request_id', 'trace_id',
  'provider', 'source', 'job_id', 'status',
  'description', 'file', 'line', 'function', 'entity',
]);

function cleanText(value, maxLength = 1000) {
  return String(value ?? '')
    .replace(/(bearer\s+)[^\s]+/gi, '$1[redacted]')
    .replace(/((?:api[_-]?key|password|token|secret)\s*[:=]\s*)[^\s,;]+/gi, '$1[redacted]')
    .replace(/https?:\/\/[^\s"<>]+/g, address => {
      try {
        const url = new URL(address);
        url.username = ''; url.password = ''; url.search = ''; url.hash = '';
        return url.href;
      } catch { return '[redacted-url]'; }
    })
    .slice(0, maxLength);
}

/** Send only selected diagnostic fields. Callers keep prompts and provider payloads local. */
export class AiLoggerClient {
  constructor({ serverUrl, project, service = 'app', environment = 'production', instanceId = null,
    fallbackJsonlPath = null, timeoutMs = 5000, fetchImpl = fetch } = {}) {
    if (!serverUrl || !project) throw new Error('serverUrl and project are required');
    const target = new URL(serverUrl);
    if (target.protocol !== 'https:' && !(target.protocol === 'http:' &&
        ['localhost', '127.0.0.1', '[::1]'].includes(target.hostname))) {
      throw new Error('HTTPS is required for remote ai_logger endpoints');
    }
    this.serverUrl = serverUrl;
    this.project = project;
    this.service = service;
    this.environment = environment;
    this.instanceId = String(instanceId ?? '').trim();
    this.fallbackJsonlPath = fallbackJsonlPath;
    this.timeoutMs = timeoutMs;
    this.fetchImpl = fetchImpl;
  }

  static fromEnv(env = process.env) {
    return new AiLoggerClient({
      serverUrl: env.AI_LOGGER_SERVER_URL,
      project: env.AI_LOGGER_PROJECT,
      service: env.AI_LOGGER_SERVICE || 'app',
      environment: env.AI_LOGGER_ENVIRONMENT || 'production',
      instanceId: env.AI_LOGGER_INSTANCE_ID,
      fallbackJsonlPath: env.AI_LOGGER_FALLBACK_JSONL_PATH || null,
    });
  }

  async send({ level = 'ERROR', logger = 'app', message, context = {}, exception = null }) {
    const normalizedLevel = String(level).toUpperCase();
    if (!LEVELS.has(normalizedLevel) || !message) throw new Error('Valid level and message are required');
    const selectedContext = {
      project: this.project, service: this.service, environment: this.environment,
    };
    if (this.instanceId) selectedContext.instance_id = cleanText(this.instanceId, 200);
    for (const [key, value] of Object.entries(context)) {
      if (CONTEXT_FIELDS.has(key) && (typeof value === 'string' || typeof value === 'number')) {
        selectedContext[key] = cleanText(value, key === 'description' ? 1000 : 200);
      }
    }
    const record = {
      id: randomUUID(), timestamp: new Date().toISOString(), logger: cleanText(logger, 200),
      level: normalizedLevel, message: cleanText(message), context: selectedContext,
    };
    if (exception && typeof exception === 'object') {
      record.exception = {
        type: cleanText(exception.type || exception.name || 'Error', 100),
        message: cleanText(exception.message, 1000),
        stack_trace: cleanText(exception.stack_trace || exception.stack, 4000),
      };
    }
    try {
      const response = await this.fetchImpl(this.serverUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify(record),
        signal: AbortSignal.timeout(this.timeoutMs),
      });
      if (!response.ok) throw new Error(`ai_logger returned ${response.status}`);
      return true;
    } catch {
      if (this.fallbackJsonlPath) {
        try {
          await mkdir(dirname(this.fallbackJsonlPath), { recursive: true });
          await appendFile(this.fallbackJsonlPath, JSON.stringify(record) + '\n', { encoding: 'utf8', mode: 0o600 });
        } catch { /* Logging must not crash the application. */ }
      }
      return false;
    }
  }
}
