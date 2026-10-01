# Served projects

`ai_logger` owns the logging backend. Each consumer has a separate directory
under `projects/<project-id>/` containing its integration code, tests,
non-secret configuration examples, connection guide and rollout instructions.
The directory name should match the consumer's `AI_LOGGER_PROJECT` value.

| Project | Integration | Status |
| --- | --- | --- |
| `ai-media-client` | [Connection guide](ai-media-client/README.md) | Metadata forwarder prepared; full error-store switch pending |

Generic clients and reusable error recording remain in `clients/`; backend
runtime and storage remain in `src/ai_logger/`. Consumer directories must not
contain credentials, private database dumps, runtime logs or generated media.

Adding a consumer requires its own directory and an entry here. Keep the
connection contract and verification steps with that consumer; link to shared
client documentation rather than duplicating shared implementations.
