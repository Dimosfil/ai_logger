# Windows 10 Agent Deployment

This folder is the no-Docker deployment entrypoint for an AI agent on Windows
10. It installs and runs the `ai_logger` server from a cloned repository.

It does not install Graylog itself. The agent must point
`AI_LOGGER_GRAYLOG_GELF_URL` at an existing Graylog GELF HTTP input, or leave the
JSONL fallback enabled while Graylog is prepared elsewhere.

## Flow

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\install.ps1
Copy-Item .\deploy\windows\env.example.ps1 .\deploy\windows\env.local.ps1
# Edit env.local.ps1 with machine-local values before starting.
powershell -ExecutionPolicy Bypass -File .\deploy\windows\start-server.ps1 -Background
powershell -ExecutionPolicy Bypass -File .\deploy\windows\check.ps1
```

Stop a background server started by this entrypoint:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\stop-server.ps1
```

The health endpoint is:

```text
http://127.0.0.1:8765/health
```

The ingest endpoint for clients is:

```text
http://127.0.0.1:8765/ingest
```

## Private Files

`env.local.ps1` contains machine-local endpoint and token values. Keep it out of
Git.
