# Project FTP Deploy

Use this pattern when the user asks `gi ftp`, `gi ftp push`, `gi ftp config`,
`gi ftp folder`, `gi ftp service`, `gi upload ftp`, `gi deploy ftp`,
`gi ftp <deploy-hub-path>`, `gi zaley na ftp`, `gi залей на фтп`, `ги фтп`,
`ги фтп <путь-к-deploy-хабу>`, `ги фтп пуш`, `ги фтп конфиг`,
`ги фтп папка`, or `ги фтп сервис`.

## Intent

- Treat `gi ftp`, `ги фтп`, `gi ftp push`, and `ги фтп пуш` as requests to
  upload the current project's configured build output through the selected
  deploy gateway. Direct FTP, FTPS, or SFTP upload is reserved for projects
  marked as deploy infrastructure with `gi set devops`, or for a documented
  deploy-gateway delegation back to the current project.
- Treat `gi ftp config`, `gi ftp конфиг`, and `ги фтп конфиг` as requests to
  create, inspect, or update FTP/SFTP config without uploading. In ordinary
  non-devops projects this means selecting or using a deploy gateway, not
  creating a project-owned personal FTP/SFTP deploy path.
- Treat `gi ftp folder`, `gi ftp папка`, and `ги фтп папка` as requests to
  inspect, choose, or update the remote upload folder (`remotePath`) without
  uploading.
- Treat `gi ftp service`, `gi ftp сервис`, and `ги фтп сервис` as requests to
  manually register, inspect, or select an FTP/FTPS/SFTP service record in
  config-service without uploading.
- Treat `gi ftp <deploy-hub-path>` and `ги фтп <путь-к-deploy-хабу>` as
  requests to upload the current project through the user-provided deploy
  gateway path. The current project remains the source; the gateway owns
  FTP/SFTP destination configuration, secret references, and the deploy
  entrypoint. Record that gateway as the current project's selected deploy
  gateway so later `gi ftp` / `ги фтп` without a path can reuse it.
- When the gateway contract supports automatic project registration, use the
  current project folder name as the default project id for an unmapped source
  project. Let the gateway derive the destination from its documented naming
  convention, register the project in its deploy registry, and record non-secret
  index metadata for later hub/card updates. Unless the gateway contract
  explicitly names an existing target hostname, the default public target is a
  project-scoped hostname, such as a sanitized project id under the gateway's
  configured base domain. Do not use the apex/root domain, shared hub hostname,
  or another project's hostname as the default target for an unmapped source.
- Keep direct FTP/SFTP settings in the deploy gateway or devops-marked project,
  not in ordinary consuming projects, chat, shared instructions, README prose,
  or global agent memory.
- Prefer `tools/deploy/ftp.local.json` only for the gateway-owned or
  devops-marked direct upload config.
- Keep `tools/deploy/ftp.local.json` untracked when it contains hostnames,
  usernames, passwords, tokens, private keys, or private remote paths.
- Commit only a redacted example such as `tools/deploy/ftp.local.example.json`
  when the project wants a documented shape.

## Config Shape

Use this JSON shape unless project-local instructions define a stricter one:

```json
{
  "protocol": "sftp",
  "host": "example.com",
  "port": 22,
  "username": "deploy",
  "passwordEnv": "PROJECT_FTP_PASSWORD",
  "privateKeyPath": null,
  "serviceId": null,
  "localPath": "dist/",
  "remotePath": "/www/example/",
  "cleanRemote": false
}
```

- `protocol` must be one of `ftp`, `ftps`, or `sftp`.
- `host`, `username`, `localPath`, and `remotePath` are required unless a
  selected `serviceId` and verified service contract supply the shared host and
  credential reference.
- `serviceId` is optional and should name the selected config-service FTP
  record when a shared FTP service is registered.
- Use `passwordEnv` or `privateKeyPath` instead of storing a password when
  practical.
- If a user explicitly provides credentials in chat, write them only to the
  project-local untracked config after confirming the destination file; do not
  echo secrets back in later messages.
- Never store FTP credentials in this shared instruction library.

## Workflow

- When a path is supplied after `gi ftp` / `ги фтп`, first read that gateway's
  local instructions and deploy runbook, then use only its documented deploy
  entrypoint. Pass the current project root as the source path using the
  gateway's documented parameter. Record the selected gateway in an ignored
  project-local file such as `tools/deploy/deploy-gateway.local.json`. Do not
  read, write, or normalize the gateway's private local config except as its own
  instructions explicitly allow.
- If the gateway has a documented deploy registry, target map, project inbox, or
  hub-card queue, treat it as gateway-owned state. For an unmapped current
  project, prefer the gateway's documented auto-registration flow. Unless the
  gateway contract names a different id source, derive `projectId` from the
  current project root folder name, then let the gateway compute the public URL,
  remote path, deploy mode, and provisioning requirements from its own
  convention. The computed public URL must be project-scoped unless an explicit
  existing mapping says otherwise; for a base domain convention this normally
  means `<sanitized-project-id>.<base-domain>`, not the apex/root domain. Record
  or verify the registry entry before the upload and leave a pending card/index
  record when the gateway uses a separate public hub or site catalog.
- Before treating an unmapped project as unknown, inspect the gateway registry
  and every documented project inbox, pending queue, hub-card queue, or
  domain/hosting request list. If the source project already has a pending or
  errored inbox/request entry, use that entry as the current deploy state. For a
  pending entry, refresh allowed non-secret metadata, upload the artifact to the
  gateway's documented pending/staging/handoff target when one exists, and
  report that devops/hosting publication is still pending instead of asking for
  a new mapping. For an errored entry or rejected request, distinguish a fresh
  error from stale evidence. A previous inbox status, old screenshot, cached
  host limit check, or indirect quota/provisioning claim is warning context, not
  proof that the current attempt will fail. When the gateway contract provides a
  safe create, refresh, or provisioning attempt for a new domain, subdomain,
  hosting slot, or public card, warn the user that provisioning may fail, run
  that attempt, then decide from the current result whether to continue artifact
  upload, leave the request pending, or return an explicit deploy error. Stop
  without attempting only when the current gateway contract has no documented
  attempt/refresh path or the current attempt returns an explicit rejection. The
  error report must name the failed domain/hosting/provisioning step, evidence,
  responsible system or owner, and next required action.
- Do not ask the user for a remote folder, project id, or subdomain when the
  gateway contract defines deterministic registration from the source project.
  Do not fall back to a gateway root/default remote path, apex/root domain,
  shared hub hostname, or another project's hostname for an unknown project.
  If auto-registration, target provisioning, or artifact selection cannot
  continue, do not report a vague blocker. A pending domain/hosting request
  should still upload to the gateway's documented pending/staging/handoff target
  when available. Otherwise return an explicit deploy error with the failed
  step, evidence, responsible system or owner, next required action, and the
  artifact/source state already recorded. Never upload the whole source
  repository or guess a destination.
- When `gi ftp` / `ги фтп` is used without a path, first check the current
  project's selected deploy gateway config. If present, use that gateway flow
  before considering any direct upload. If the project is not marked devops and
  no documented gateway delegation exists, do not fall back to
  `tools/deploy/ftp.local.json`; ask one short question for the deploy gateway
  path. Direct project-local FTP/SFTP upload config is allowed only in a devops
  project or through explicit gateway delegation.
- For `gi ftp service` / `ги фтп сервис`, read the configured
  `configServiceUrl` only when project config-service integration is enabled and
  only in a devops project or documented gateway delegation,
  query config-service for services whose contract declares FTP, FTPS, or SFTP
  capability, and either register the user-provided service metadata or write
  the selected `serviceId` into the gateway-owned or devops FTP config. In
  ordinary non-devops projects, service selection belongs to the saved or
  supplied deploy gateway. Do not upload during this command.
- If a devops project or delegated gateway flow needs FTP,
  `tools/deploy/ftp.local.json` has no `serviceId`, and project config-service
  integration is enabled, check config-service before asking the user for host
  details. When integration is disabled, use only documented local or gateway
  config.
- If one matching FTP-capable service exists, use it after reading and verifying
  its contract.
- If several matching services exist, ask the user to choose with the plain
  inline numbered checkbox marker style used by `gi language`, for example
  `[ ] 1. Display name (service-id)`. Accept numeric replies against that latest
  checklist.
- If no matching service exists, offer `gi ftp service` as the command to
  register one manually, then continue with project-local config only if the
  user provides details for this project.
- Store only non-secret discovery metadata in config-service: service id,
  display name, protocol, base URL or host/port when policy allows it,
  endpoint paths, capability tags, and secret reference names such as
  `passwordEnv`. Never store raw passwords, tokens, private keys, or private
  remote paths in config-service.
- For `gi ftp config` / `ги фтп конфиг`, ordinary non-devops projects create,
  inspect, or update only selected-gateway metadata such as
  `tools/deploy/deploy-gateway.local.json`. Create or update
  `tools/deploy/ftp.local.json` from the template shape only in a devops project
  or documented gateway delegation, ask only for missing required values, and
  remind the user when secrets are referenced through environment variables
  instead of stored in the file.
- For `gi ftp folder` / `ги фтп папка`, inspect or update only `remotePath`.
  In ordinary non-devops projects, resolve this through the selected deploy
  gateway and do not create a project-owned direct remote path. In a devops
  project or documented gateway delegation, if the user provides a path,
  validate that it is a remote deploy folder and save it to the gateway-owned or
  devops FTP config. If the user asks to choose a folder, list remote
  directories through the configured FTP service or project-local credentials
  when available, present a short plain inline numbered checkbox marker list,
  and accept numeric replies against that latest checklist. Do not upload files
  during this command.
- When writing config values, preserve existing fields unless the user asks to
  change them.
- When showing config status, redact `host`, `username`, `password`,
  `passwordEnv` values that reveal private names, `privateKeyPath`, and private
  remote paths unless the user explicitly asks to inspect the local file.
- Read project-local instructions, runbook, package/build manifests, selected
  deploy-gateway metadata, and, only for devops or delegated direct upload,
  `tools/deploy/ftp.local.json` before asking for upload details.
- If direct-upload config is missing in an allowed devops or delegated context,
  look for a redacted example in `tools/deploy/ftp.local.example.json`, then ask
  the user for the missing non-secret details and where they want secrets stored.
- If `localPath` is missing or stale, run the documented production build before
  upload. If no build contract exists, ask one short clarification question.
- Prefer existing project deploy scripts when they read the same config and do
  not expose secrets in command output.
- If no deploy script exists, use an available standard tool appropriate to the
  protocol, such as WinSCP, `sftp`, `scp`, `lftp`, or `curl`, without printing
  secrets.
- Treat an upload stall, hang, repeated timeout, or failed stream open as a
  failed FTP/FTPS transfer. Do not keep extending the same FTP attempt or cycle
  through passive/active/FTPS variants as a substitute for the documented
  fallback.
- When FTP or FTPS connects but uploads fail, stall, or repeatedly time out,
  immediately inspect the project-local config, selected service contract, and
  current user-provided deployment details for an SSH-based SFTP route. If they
  supply the SSH host, port, user, credential reference, and same documented
  remote deploy folder, switch to SFTP over SSH before trying more FTP/FTPS
  upload variants. Treat SFTP over SSH as a valid fulfillment of `gi ftp`.
  Report that SFTP over SSH was used as the fallback.
- If the SFTP route is missing required connection details, stop and report the
  exact missing fields or ask one short question for them. Do not invent SSH
  credentials, private-key paths, or remote paths, and do not keep retrying the
  same failing FTP transfer when an authorized SFTP route is available.
- Do not disable TLS certificate validation, accept an invalid FTPS certificate,
  or treat an invalid-certificate FTPS connection as the routine fallback for a
  failing FTP upload unless the project-local deploy contract or the current
  user message explicitly authorizes that risk. Report any such exception as a
  degraded security path.
- Do not delete or replace remote files unless `cleanRemote` is true and the
  project-local instructions or user request clearly allow that behavior.
- After upload, report the protocol, host, remote path, local artifact path, and
  verification performed. Do not print passwords, tokens, private keys, or full
  credential-bearing command lines.

## Verification

- Confirm the local upload source exists before starting transfer.
- Prefer a dry listing or checksum/size comparison when the tool and server
  support it.
- If verification cannot be performed, say so briefly and report the transfer
  command result without exposing secrets.
