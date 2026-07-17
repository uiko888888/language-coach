# Deployment Architecture

## Product Form

Language Coach should become a hosted Web/PWA for general users, with an optional local companion for private files and local-only integrations.

| Capability | Hosted Web/PWA | Local companion |
| --- | --- | --- |
| Public articles and scheduled refresh | Primary | Local cache |
| Accounts, profiles and cross-device sync | Primary | Not required |
| Exercises, dictionary and progress | Primary | Offline/private fallback |
| EPUB, private subtitles and local dictionaries | Metadata only | Primary |
| User-owned API keys | Server vault or bring-your-own-key policy | Local `.env.local` |
| Browser extension bridge | HTTPS API | Loopback API for private captures |

The hosted scheduler must refresh shared public sources independently of any user's computer. The local scheduler is a transition feature for the current single-user edition and a future companion feature; it is not the final public deployment model.

## Current Windows Local Edition

Install the per-user sign-in task from the project directory:

```powershell
.\scripts\install_windows_autostart.ps1
```

It starts the backend 30 seconds after Windows sign-in. The backend checks stale feeds at startup and then checks every six hours while the computer is awake. It does not run while the computer is powered off; missed startup runs are recovered at the next sign-in.

Check status or remove the task:

```powershell
.\scripts\windows_autostart_status.ps1
.\scripts\uninstall_windows_autostart.ps1
```

To use another port consistently:

```powershell
$env:LANGUAGE_COACH_PORT = "8766"
.\scripts\install_windows_autostart.ps1 -Port 8766
```

The task runs only for the current Windows user, starts the backend directly, prevents parallel task instances, retries startup failures three times, and starts missed runs when possible. Uninstalling it does not terminate an already running Python process.

## Public Release Path

1. Split the current Python file into API, content, training, dictionary and worker modules.
2. Add accounts, permissions and a server database migration path.
3. Move public feed refresh into a cloud worker and durable queue.
4. Add object storage only for licensed/public assets; keep private book text out by default.
5. Ship a responsive PWA, then retain the Windows companion only for local files, dictionaries and extension privacy.
6. Add monitoring, backups, rate limits, abuse controls and data deletion before public registration.
