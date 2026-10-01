-- Apply explicitly to the logger-owned database, not a consumer's application database.
CREATE TABLE IF NOT EXISTS ai_logger_system_errors (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project text NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  source text NOT NULL,
  event text NOT NULL,
  code text,
  message text NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ai_logger_system_errors_recent
  ON ai_logger_system_errors(project, occurred_at DESC, id DESC);
