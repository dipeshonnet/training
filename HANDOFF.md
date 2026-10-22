# Continue AI Coach v2 deployment

Updated: 21 October 2026 (Asia/Kolkata).

### People CSV import — 22 October 2026

Learning operations now includes **People & access: import CSV** for administrators and trainers, with a downloadable template and per-row results. The server endpoint is `bpo_coach.people_import.import_people` (POST, authenticated staff only). Files are limited to 500 KB and 100 people, matched by normalized email. Headers are `name,email,password,role,batchIds`; roles are `learner`, `trainer`, and `admin`. Passwords are required only for new accounts. Blank roles preserve existing roles; batch IDs separated by semicolons add memberships without removing existing ones.

Trainers can manage ordinary learner accounts only. Existing learners must have all batch memberships in the trainer's assigned processes. New learners need an accessible batch; native LMS enrollment also requires the trainer to be an instructor or evaluator for that batch. Administrator role changes replace managed BPO/LMS role pairs and remove stale trainer process access. Importing does not grant old assignments to new batch members.

Rows use database savepoints and discard queued transaction callbacks on failure, so a native validation failure cannot leave a newly created account behind. Errors do not expose passwords or framework exception details. Verification includes CSV parser tests, Vue component tests and real Frappe integration tests in `bpo_coach.tests.test_people_import`. No schema migration is required. This feature does not close the broader public rollout gates below.

## Status: local Docker verification; public deployment gates remain open

The site has been initialized locally at `127.0.0.1:8080` with canonical Host `training.everydayai.work`. MariaDB, Redis, backend, workers, scheduler, websocket and Nginx run under Compose project `ai-coach-v2`. Docker Desktop is working on this Windows host. Local credentials are private in ignored `deploy/.env`; database/site volumes contain disposable verification data only. No real training data has been migrated, public tunnel configured, release image published or verified release tag created.

Work remains on `ai-coach-v2` in `https://github.com/dipeshonnet/training`. Keep the stable application pins below. `deploy/versions.json` intentionally remains `development-unverified`; base and service images now have exact digest locks.

### Completed foundation milestones

- Built both Docker image targets, installed Payments/LMS/BPO Coach, migrated the site and verified native/custom assets through Nginx. Initialization resumes interrupted installs, preserves administrator configuration and can be repeated. Windows CRLF source normalization is performed only after all pinned-source hashes and patch states pass.
- Verified real Administrator login, guest private-file denial, authenticated private-file retrieval, public-file bytes, internal-route denial and `/coach`. CI uses the actual hashed File URLs returned by Frappe. These probes also pass after restart.
- Added Nginx dynamic upstream resolution and a frontend health check that reaches Frappe. A disposable DNS probe replaces the backend at a different address while preserving volumes. The probe uses two temporary backend replicas so it works on Docker engines that disallow explicit IPs on automatically allocated subnets.
- Added scoped native course catalog/count/details/outline/lesson adapters. Filters apply before upstream pagination. Nine custom Frappe integration tests cover installation/schema/roles, storage and representative learner/native visibility paths, including draft company-wide content and enrollment filters. This is partial permission coverage; the broader native paths below remain open.
- Version-specific LMS compatibility patches address search-index continuation, DocPerm helper imports, certificate mapper documents, binary image attachments, ZIP upload fixtures and imported asset URL preservation. Media tests cover reuse of identical orphan files and rejection of different existing bytes. Redaction tests still assert that real secret canaries are hidden and authorized authors/graders retain access; null redacted keys are normalized for released Frappe.
- Native frontend uses the browser origin for production realtime traffic. A hash-checked Frappe Node patch forwards the validated site header to the configured internal backend. Nginx preserves supplied browser origins. `deploy/smoke_socketio.py` exercises authenticated namespace connections and denial of invalid origins and guests.
- New internal sites disable signup/guest catalog access and skip native persona collection, which otherwise submits to an external service. Completed setups retain administrator choices. The disposable existing local training site was explicitly brought to these defaults.
- Standalone rules: 14 pass. Deployment contracts: 10 checks (Windows symlink check skips; actual Linux asset materialization passed). Custom frontend: four bridge tests and production build pass. Native frontend checkpoint CI passed 1,571 tests across 153 files and a production build through `b864eba`. The local production bundle also builds with a 4 GB Node heap.

### Native server verification

The full local native LMS suite passes on the pinned stack: 75 unit tests, 961 integration tests, 78 ordinary tests (three upstream skips) and 167 additional unit tests; 1,281 tests total. The badge fixture cleanup clears the released Frappe client-cache map after rollback. All nine custom integration tests pass with the internal-site settings assertions.

Checkpoint and full Docker foundation build/test gates pass at `b864eba`: [checkpoint run](https://github.com/dipeshonnet/training/actions/runs/39628158455), [Docker foundation run](https://github.com/dipeshonnet/training/actions/runs/39628158414). Both images were built from committed sources, followed by fresh initialization, asset/file/login checks, repeated initialization/restart, forced backend address replacement, authenticated realtime/invalid-origin/guest checks, nine custom tests and the full native suite. Nginx connection attempts are bounded to three seconds; the DNS probe requires sustained recovery before checking session/file controls.

The browser additionally exposed Frappe UI's automatically created second socket on port 9000. Commit `b864eba` disables that duplicate and shares LMS's configured client between Vue injection and global properties. A fresh browser verified both references are identical and connected over WebSocket through port 8080, with zero port-9000 requests. Desktop sidebar and mobile You → AI Coach navigation both open `/coach`; the 390 px portal and Scenario studio have no horizontal overflow. File/login and realtime positive/negative probes pass after the final image replacement. The final shared-client change also passes both CI workflows at `b864eba`.

Local app/frontend tags include development verification overlays and must not be published as release images. `allow_tests` was disabled again on both local sites after the successful run. Keep `lms-baseline.local` disposable and remove it before public exposure.

Next: continue the access-control, assignment/curriculum, EditorJS scenario, backup/restore and browser/provider gates below. Keep the tunnel profile off until those gates pass.

## 1. Clone the correct branch

```bash
git clone --branch ai-coach-v2 https://github.com/dipeshonnet/training.git
cd training
git status
```

The repository's default branch may still be `develop`; explicitly select `ai-coach-v2`. Continue committing and pushing to this branch. Do not force-push or merge it over `develop` just to change the deployment baseline.

## 2. Understand the layout and pins

| Location | Purpose |
|---|---|
| Repository root / `lms` / `frontend` | Stable upstream Learning application and its native Vue frontend |
| `apps/bpo_coach/bpo_coach` | Separate Frappe app: metadata, access checks, APIs, rules, grading jobs and completion hooks |
| `apps/bpo_coach/frontend` | Custom Vue portal, scenario builder, simulation player, operations screens and SOP exporter |
| `apps/bpo_coach/tests` | Pure Python rules tests and checked-in pilot parity fixtures |
| `deploy` | Pinned Docker/Compose/Nginx, compatibility patches, HTTP/realtime/DNS probes and version manifest |

Target application revisions:

- LMS `v2.66.0`: `aa8b53b0a7e940871cdb006962a212daccb52a09`.
- Frappe `v16.52.0`: `4515014c87ece6cb20ee91d2cfb121c5cbd1ff4a`.
- Payments `version-16`: `cca07d9f9392e2ea0e521c5975151db9e4b6c321`.
- Python 3.14, Node 24, MariaDB 11.8, Redis 7, Bench 5.29.1.

`deploy/versions.json` records the pins and intentionally says `development-unverified`. Container base and service digests are recorded in the Dockerfile, Compose file and version manifest. Keep secrets and real site data out of this public repository.

## 3. Run the checks that currently work

Use Python 3.14 and Node 24 on the destination. The rules tests were also run successfully with the previous machine's Python 3.13.14; this does **not** establish Frappe compatibility with Python 3.13.

Linux/macOS/WSL:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install jsonschema==4.26.0
PYTHONPATH=apps/bpo_coach python -m unittest discover -s apps/bpo_coach/tests -v
python -m compileall -q apps/bpo_coach/bpo_coach deploy
cd apps/bpo_coach/frontend
npm ci
npm run build
cd ../../..
```

PowerShell (after creating/activating a suitable Python environment):

```powershell
python -m pip install jsonschema==4.26.0
$env:PYTHONPATH = Join-Path (Get-Location) 'apps/bpo_coach'
python -m unittest discover -s apps/bpo_coach/tests -v
python -m compileall -q apps/bpo_coach/bpo_coach deploy
Set-Location apps/bpo_coach/frontend
npm ci
npm run build
Set-Location ../../..
```

Observed before handoff:

- Fourteen pure Python tests pass. The scoring parity test covers 160 generated cases from the existing pilot engine, including action scoring, completion, weighted grading and evidence validation.
- Unicode answer normalization and assessment redaction fixtures pass.
- Custom Vue production build succeeds. It emits `main.js` and `main.css`; the main JavaScript bundle currently exceeds Vite's advisory 500 kB threshold.
- Python source compilation passes.
- Native frontend tests/build, custom Frappe integration, HTTP controls and basic desktop portal navigation have run. The full native server suite also passes; see the counts above. Microphone, live Groq, load and the remaining feature interactions are outstanding.

The custom frontend has four EditorJS bridge tests. Desktop and 390 px mobile portal/Scenario studio navigation were checked; neither mobile screen overflowed horizontally. Run `npm test` as well as `npm run build`. The microphone, builder, simulation and SOP interaction tests remain outstanding. Run deployment contract checks with `python -m unittest discover -s deploy -p 'test_*.py' -v`; the patch tests need the pinned LMS commit available in Git history.

The parity fixture is committed and does not require the original pilot checkout to run. `deploy/generate_parity.mjs` is a developer utility that needs the original pilot source path if regenerating fixtures; do not regenerate expected outputs to hide a scoring regression.

## 4. Fix these blockers before trying to deploy

1. **LMS integration needs feature verification:** the pinned bridge patch and native frontend CI pass. Desktop/mobile navigation and same-origin realtime pass in a live browser. Verify actual EditorJS authoring/rendering with assigned AI scenarios. The tool implementation is `apps/bpo_coach/frontend/src/bridge.js`.
2. **Native access paths need integration coverage:** custom API scope checks, hooks and six native read adapters have representative integration coverage. Audit and test native LMS whitelisted methods, SQL/search/report paths, direct document writes and file access; do not assume document hooks cover queries that bypass them. Tighten any scope bypasses before public exposure.
3. **Docker asset/file foundation passes locally:** asset materialization and Nginx public/private/internal routing probes pass. Keep these checks in CI and verify scoped uploaded course media with representative non-administrator users.
4. **Frappe install/bootstrap passes locally:** custom DocTypes/roles, separate app installation, migration and retry recovery have run. Continue native batch/course/enrollment and interrupted-upgrade coverage against the pinned versions.
5. **Missing operational features:** encrypted backup/restore and R2 upload tooling, portable setup/upgrade commands, the read-only pilot exporter/importer, verified release-image publication and digest recording are not implemented. Import/reminder record metadata alone is not an importer.
6. **CI remains partial:** checkpoint CI now includes rules/install/deployment/bridge tests and a patched native frontend test/build. Docker foundation CI is green through fresh builds, initialization, HTTP/restart, DNS/realtime and the full native suite through the final frontend change at `b864eba`. Browser, full native permission integration and release publication gates remain outstanding. Inherited upstream release/image jobs have fork guards.

Other targeted follow-ups:

- Exercise assignment replay/conflicting request IDs and add payload-fingerprint checks where necessary; verify concurrent submit/review/grading behaviour and recovery across process restarts.
- Verify foundation-course publishing and trainer access without granting cross-process native privileges. Ensure draft company-wide content is not exposed to learners.
- Verify assigned course/lesson/quiz structure locking through every native editing and deletion path, including direct database updates in native endpoints.
- Validate AI channel bindings against scenario office type and scope when saving lessons and assigning courses.
- Test submitted-attempt redaction, critical-failure enforcement and certificates through direct REST and native endpoints.
- Add frontend tests for microphone denial, audio cleanup, refresh/retry behaviour, hotspot drawing and authenticated SOP screenshot download.
- The SOP document generator and scenario types were copied from the original React pilot; screenshots now resolve through the Frappe API adapter. Browser export has not yet been verified.
- Split the SOP/builder bundle from the learner entry point and verify the custom UI visually on desktop and mobile.
- Add worker/scheduler/backup health checks and ensure native publication/signup/settings defaults behave as intended.

## 5. Bring up a development site after the blockers are fixed

First ensure `docker version` reports both Client and Server. Prefer a clean Linux Docker host for integration verification.

```bash
cp deploy/.env.example deploy/.env
# Privately fill DB_ROOT_PASSWORD and ADMIN_PASSWORD with strong random values.
# Add GROQ_API_KEY only when ready for live provider verification.
docker compose --env-file deploy/.env -f deploy/compose.yaml config --quiet
docker compose --env-file deploy/.env -f deploy/compose.yaml build
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d
docker compose --env-file deploy/.env -f deploy/compose.yaml ps
docker compose --env-file deploy/.env -f deploy/compose.yaml logs --tail 100 initialize backend
```

These commands have initialized and started the local verification site. A clean build from the latest committed sources is still required before release. The default local frontend binds to `127.0.0.1:8080`; configure local DNS/hosts for `training.everydayai.work` while testing, or send its Host header when checking the origin. Do not change public DNS to an unverified site.

The initializer installs Payments, LMS and `bpo_coach` on a new site. The backend entry point passes through explicit Bench commands, for example:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml exec backend bench --site training.everydayai.work list-apps
docker compose --env-file deploy/.env -f deploy/compose.yaml exec backend bench --site training.everydayai.work set-config allow_tests true
docker compose --env-file deploy/.env -f deploy/compose.yaml exec backend bench --site training.everydayai.work run-tests --app bpo_coach
```

Run native LMS tests on a separate disposable baseline site with Payments and LMS only, matching Docker CI. The restricted training site intentionally changes upstream guest-access assumptions. The custom Bench tests live in `apps/bpo_coach/bpo_coach/tests`; standalone rules remain in `apps/bpo_coach/tests`.

## 6. Complete the original feature and deployment gates

Finish and verify, in order:

1. **Foundation verified locally and in CI:** repeatable stable Docker installation, restart persistence, DNS/realtime recovery and native baseline checks. Preserve these gates as later features change.
2. Clients/processes/process access, company-wide foundations, scoped batches, explicit enrollment, individual/batch assignments, due dates, learner resume and curriculum locks.
3. Screenshot authoring, click/input regions, accepted answers, distractors/critical failures, rubrics, immutable publication, SOP export and AI lesson blocks.
4. Workflow/chat/turn-based voice delivery, walkthrough/practice/assessment separation, resumability, idempotency, Groq conversation/coaching/transcription/speech and recoverable grading.
5. Trainer evidence/review, per-channel passing assessment plus approval, required quiz passes, graded assignment Pass and server-enforced certificate eligibility.
6. Reports and CSV exports, first-attempt metrics excluding practice/walkthrough/provider processing failures, daily deduplicated in-app reminders at 09:00 Asia/Kolkata, repeatable pilot content import.
7. Backup encryption, private R2 backups, restoration on a clean second machine, release-tagged GHCR images, digest locks and upgrade recovery.
8. External browser and microphone workflows plus a 25-user browser test with simulated provider responses, followed by limited real Groq checks.

Pilot defaults: English; Asia/Kolkata; administrator-created users; up to 100 accounts and a target of 25 concurrent portal users subject to testing and Groq limits; 60-second turn-based recordings. Retain transcripts, actions, scores and reviews; discard processed audio. Only administrators publish company-wide content. Later batch members require an explicit assignment action. Practice and walkthrough never satisfy assessment completion.

## 7. Publish the verified portal through Cloudflare

`training.everydayai.work` is the chosen canonical hostname. The domain already uses Cloudflare nameservers. Cloudflare provides the public entry point; the application still needs a running Docker host. Render and a new VM subscription are not required for the initial PC-hosted pilot.

After the acceptance checks pass:

1. Create a named tunnel in the Cloudflare account controlling `everydayai.work`.
2. Route `training.everydayai.work` to `http://frontend:8080` when running `cloudflared` inside this Compose network.
3. Store its token privately in `deploy/.env` as `CLOUDFLARE_TUNNEL_TOKEN`.
4. Start the optional connector with `docker compose --env-file deploy/.env -f deploy/compose.yaml --profile online up -d tunnel`.
5. Verify HTTPS host routing, Frappe login/CSRF cookies, websockets, private files, microphone permission, retries and certificates from an external browser.
6. Cache versioned public assets only; bypass Cloudflare caching for authenticated pages, APIs and private files.

No tunnel token or Groq/R2 credentials are included in Git. Base and service images, including the tunnel connector, have digest pins. The public tunnel connection and external-browser behaviour remain untested.

For moving a real site, pause writes and jobs, take a final encrypted database/files/site-configuration backup, restore on the destination with the matching application release and encryption key, test it, then transfer the tunnel connection. Do not run tunnel replicas against independent copies of the database. Git alone does not carry site data.

## Historical machine issue

The current Docker engine is working, and verification volumes were preserved. Earlier, Docker Desktop's backend failed to start on the previous Windows machine with an inaccessible Unix socket/reparse-point error for `%LOCALAPPDATA%\Docker\run\sailor-ingest.sock` (Windows error 1920). CLI restart and stale-socket cleanup attempts did not fix it. Its old runtime directory was preserved as `%LOCALAPPDATA%\Docker\run-recovery-20261021`; containers/database volumes were not removed. Further repair of that Windows installation is not required to continue on another machine with a working engine.

## Suggested prompt for the next agent

> Continue AI Coach v2 from the ai-coach-v2 branch of https://github.com/dipeshonnet/training. Read HANDOFF.md and deploy/versions.json first. This is an unfinished checkpoint, not a deployed release. Keep stable LMS v2.66.0, Frappe v16.52.0 and the pinned Payments version-16 revision. The local Docker foundation, pinned compatibility patches, full native baseline, HTTP/restart/DNS/realtime checks and desktop/mobile navigation are verified. Check the latest CI links and continue the remaining native permission, assignment/curriculum and EditorJS scenario gates; do not redo completed bootstrap work. Finish the remaining feature, permission, completion, migration, encrypted backup/restore and browser/provider/load gates listed in HANDOFF.md. Commit and push tested milestones. Configure training.everydayai.work through Cloudflare only after local integration and access-control checks pass. Keep credentials and real training data outside Git; do not publish a verified release tag until its gates pass.
