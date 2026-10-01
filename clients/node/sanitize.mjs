/** Portable diagnostic sanitizer extracted from ai-media-client's generation journal. */
export function createSanitizer() {
  const secrets = new Set();
  function secret(value) {
    if (typeof value === 'string' && value.length > 5) secrets.add(value);
  }
  function clean(value, key = '', depth = 0) {
    if (/authorization|cookie|token|password|api.?key|secret/i.test(key)) return '[REDACTED]';
    if (depth > 12) return '[DEPTH LIMIT]';
    if (value instanceof Error) return {
      name: clean(value.name, '', depth + 1), message: clean(value.message, '', depth + 1),
      code: clean(value.code, '', depth + 1),
      stack: clean(value.stack, '', depth + 1),
      cause: value.cause ? clean(value.cause, '', depth + 1) : undefined,
    };
    if (Buffer.isBuffer(value) || value instanceof Uint8Array) return { bytes: value.byteLength };
    if (typeof value === 'string') {
      if (/^[\[{]/.test(value.trim())) {
        try { return clean(JSON.parse(value), '', depth + 1); } catch { /* ordinary text */ }
      }
      for (const item of secrets) value = value.split(item).join('[REDACTED]');
      return value.replace(/Bearer\s+[^\s"']+/gi, 'Bearer [REDACTED]')
        .replace(/\b\d{6,}:[A-Za-z0-9_-]{20,}/g, '[REDACTED]')
        .replace(/((?:api[_-]?key|password|token|secret)\s*[:=]\s*)[^\s,;]+/gi, '$1[REDACTED]')
        .replace(/https?:\/\/[^\s"<>]+/g, address => {
          try {
            const url = new URL(address);
            url.username = ''; url.password = ''; url.search = ''; url.hash = '';
            return url.href;
          } catch { return '[URL]'; }
        }).slice(0, 32768);
    }
    if (Array.isArray(value)) return value.slice(0, 100).map(item => clean(item, '', depth + 1));
    if (value && typeof value === 'object') return Object.fromEntries(
      Object.entries(value).slice(0, 100).map(([k, v]) => [k, clean(v, k, depth + 1)]),
    );
    return typeof value === 'bigint' ? String(value) : value;
  }
  return { clean, secret };
}
