import { appendFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';
import { randomUUID } from 'node:crypto';

const LEVELS = new Set(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']);
const CONTEXT_FIELDS = new Set([
  'component', 'operation', 'error_code', 'request_id', 'trace_id',
  'provider', 'source', 'job_id', 'status',
]);

function cleanText(value, maxLength = 1000) {
  return String(value ?? '')
    .replace(/(bearer\s+)[^\s]+/gi, '$1[redacted]')
    .replace(/((?:api[_-]?key|password|token|secret)\s*[:=]\s*)[^\s,;]+/gi, '$1[redacted]')
    .slice(0, maxLength);
}

/** Send only selected diagnostic fields. Callers keep prompts and provider payloads local. */
export class AiLoggerClient {
  constructor({ serverUrl, apiKey, project, service = 'app', environment = 'production',
    fallbackJsonlPath = null, timeoutMs = 5000, fetchImpl = fetch } = {}) {
    if (!serverUrl || !apiKey || !project) throw new Error('serverUrl, apiKey and project are required');
    const target = new URL(serverUrl);
    if (target.protocol !== 'https:' && !(target.protocol === 'http:' &&
        ['localhost', '127.0.0.1', '[::1]'].includes(target.hostname))) {
      throw new Error('HTTPS is required for remote ai_logger endpoints');
    }
    this.serverUrl = serverUrl;
    this.apiKey = apiKey;
    this.project = project;
    this.service = service;
    this.environment = environment;
    this.fallbackJsonlPath = fallbackJsonlPath;
    this.timeoutMs = timeoutMs;
    this.fetchImpl = fetchImpl;
  }

  static fromEnv(env = process.env) {
    return new AiLoggerClient({
      serverUrl: env.AI_LOGGER_SERVER_URL,
      apiKey: env.AI_LOGGER_API_KEY,
      project: env.AI_LOGGER_PROJECT,
      service: env.AI_LOGGER_SERVICE || 'app',
      environment: env.AI_LOGGER_ENVIRONMENT || 'production',
      fallbackJsonlPath: env.AI_LOGGER_FALLBACK_JSONL_PATH || null,
    });
  }

  async send({ level = 'ERROR', logger = 'app', message, context = {} }) {
    const normalizedLevel = String(level).toUpperCase();
    if (!LEVELS.has(normalizedLevel) || !message) throw new Error('Valid level and message are required');
    const selectedContext = {
      project: this.project, service: this.service, environment: this.environment,
    };
    for (const [key, value] of Object.entries(context)) {
      if (CONTEXT_FIELDS.has(key) && (typeof value === 'string' || typeof value === 'number')) {
        selectedContext[key] = cleanText(value, 200);
      }
    }
    const record = {
      id: randomUUID(), timestamp: new Date().toISOString(), logger: cleanText(logger, 200),
      level: normalizedLevel, message: cleanText(message), context: selectedContext,
    };
    try {
      const response = await this.fetchImpl(this.serverUrl, {
        method: 'POST',
        headers: { Authorization: `Bearer ${this.apiKey}`, 'Content-Type': 'application/json; charset=utf-8' },
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
