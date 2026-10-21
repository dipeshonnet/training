# Continue AI Coach v2 on another machine

Updated: 21 October 2026 (Asia/Kolkata).

## Status: unfinished development checkpoint

### Continuation milestone (21 October 2026)

- Added the missing version-specific LMS bridge patch and source hashes. The image build now registers `ai_coach` in the shared EditorJS tools, plus authenticated desktop/mobile navigation. Patch tests verify the pinned upstream sources, repeat application, and rejection of drift or a partial patch. Native interaction/build verification is still pending CI.
- Asset export now follows Bench symlinks into real files before the Nginx image copy. Fixed private-file routing to include the site directory and request Frappe's authenticated `X-Accel-Redirect` response. Added public-file routing with a restrictive content policy. Actual Nginx/file checks await Docker CI.
- Initialization now resumes individual app installs, migrates explicitly, and preserves extra common configuration. Required roles are created before custom DocType sync. Migration can finish interrupted initial defaults without resetting later administrator changes.
- Added custom EditorJS tests, deployment contract tests, pinned native frontend CI, and a Docker foundation workflow covering initialization, file/login probes, restart recovery and native LMS server tests. Inherited release/image publication jobs are restricted to `frappe/lms`; this fork needs its own verified release workflow before publishing images.
- Local checks: 13 Python rules/install tests, 7 deployment tests and 4 frontend bridge tests pass; one real symlink-export test is skipped because this Windows account cannot create symlinks. Custom production build and source compilation pass. Local Python is the bundled 3.12.14, so this does not verify the target Python 3.14 runtime; CI uses 3.14. No Docker executable/engine is available here. Native, Linux symlink and Docker gates are not yet recorded as passed.

Continue with the CI results for this milestone, then the remaining native access-control and feature gates below. No public deployment or verified release is authorized by a successful unit test run alone.

CI for `89443a9fac468f9a73081800a706bbc34df421f5`: the Linux Python 3.14/custom frontend job passed all 25 checks, including real symlink materialization. The first Docker build failed because Bench tried to configure host cron (`/usr/bin/crontab` is absent). Added Bench 5.29.1's supported `--no-backups` option; the dedicated encrypted-backup work remains outstanding. Docker must be rerun after this correction. Native frontend CI is still pending.

This commit preserves implementation work so development can continue on a working Docker host. **Do not treat it as a completed, secure or deployable release.** No site has been initialized, no training data migrated, no Cloudflare Tunnel configured, no GHCR image published, and no verified release tag created.

The upstream LMS code is based on the released `v2.66.0` tag, not the previous development fork. Existing `develop` history remains separate. Work is on `ai-coach-v2` in `https://github.com/dipeshonnet/training`.

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
| `deploy` | Initial Docker, Compose, Nginx, version manifest and schema-generation files |

Target application revisions:

- LMS `v2.66.0`: `aa8b53b0a7e940871cdb006962a212daccb52a09`.
- Frappe `v16.52.0`: `4515014c87ece6cb20ee91d2cfb121c5cbd1ff4a`.
- Payments `version-16`: `cca07d9f9392e2ea0e521c5975151db9e4b6c321`.
- Python 3.14, Node 24, MariaDB 11.8, Redis 7, Bench 5.29.1.

`deploy/versions.json` records the pins and intentionally says `development-unverified`. Container digests have not yet been resolved. Keep secrets and real site data out of this public repository.

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

- Nine pure Python tests pass. The scoring parity test covers 160 generated cases from the existing pilot engine, including action scoring, completion, weighted grading and evidence validation.
- Unicode answer normalization and assessment redaction fixtures pass.
- Custom Vue production build succeeds. It emits `main.js` and `main.css`; the main JavaScript bundle currently exceeds Vite's advisory 500 kB threshold.
- Python source compilation passes.
- Native LMS/Frappe tests, frontend interaction tests, browser/microphone tests, live Groq checks and load tests have **not** run against this implementation.

The custom frontend now has four EditorJS bridge tests. Run `npm test` as well as `npm run build`. The microphone, builder, simulation and SOP interaction tests remain outstanding. Run deployment contract checks with `python -m unittest discover -s deploy -p 'test_*.py' -v`; the patch tests need the pinned LMS commit available in Git history.

The parity fixture is committed and does not require the original pilot checkout to run. `deploy/generate_parity.mjs` is a developer utility that needs the original pilot source path if regenerating fixtures; do not regenerate expected outputs to hide a scoring regression.

## 4. Fix these blockers before trying to deploy

1. **LMS integration needs native verification:** the missing `deploy/patches/lms-ai-coach.patch` is implemented and tested against the pinned sources. Verify the patched native frontend CI and actual EditorJS authoring/rendering and navigation in a live site. The tool implementation is `apps/bpo_coach/frontend/src/bridge.js`.
2. **Native access paths need integration coverage:** custom API scope checks and Frappe hooks are initial code only. Audit and test native LMS whitelisted methods, SQL/search/report paths, direct document writes and file access; do not assume document hooks cover queries that bypass them. Tighten any scope bypasses before public exposure.
3. **Docker asset handling needs execution:** asset export now materializes symlink targets, and Nginx routes private files through the site directory. Run the Linux symlink test and Docker HTTP probes for native/custom assets, guest denial, authenticated private-file retrieval and internal-route denial.
4. **Frappe install/bootstrap needs execution:** verify custom DocTypes and roles sync in the correct order, separate app installation, `after_migrate`, native batch/course required fields and enrollment behaviour against the pinned versions. Confirm the Bench command options and dependencies during an actual build.
5. **Missing operational features:** encrypted backup/restore and R2 upload tooling, portable setup/upgrade commands, the read-only pilot exporter/importer, verified release-image publication and digest recording are not implemented. Import/reminder record metadata alone is not an importer.
6. **CI remains partial:** checkpoint CI now includes rules/install/deployment/bridge tests and a patched native frontend test/build. Docker foundation CI was added but has not been verified yet. Browser, full native permission integration and release publication gates remain outstanding. Inherited upstream release/image jobs have fork guards.

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

These are the intended commands for the current scaffold, **not previously verified installation instructions**. The default local frontend binds to `127.0.0.1:8080`; configure local DNS/hosts for `training.everydayai.work` while testing, or send its Host header when checking the origin. Do not change public DNS to an unverified site.

The initializer installs Payments, LMS and `bpo_coach` on a new site. The backend entry point passes through explicit Bench commands, for example:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml exec backend bench --site training.everydayai.work list-apps
docker compose --env-file deploy/.env -f deploy/compose.yaml exec backend bench --site training.everydayai.work set-config allow_tests true
docker compose --env-file deploy/.env -f deploy/compose.yaml exec backend bench --site training.everydayai.work run-tests --app lms
```

Add native Frappe integration tests for the custom app and run them through Bench. The existing `apps/bpo_coach/tests` directory currently contains standalone rules tests only.

## 6. Complete the original feature and deployment gates

Finish and verify, in order:

1. Repeatable stable Docker foundation, restart persistence and native baseline checks.
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

No tunnel token or Groq/R2 credentials are included in Git. The Cloudflare tunnel image tag and other mutable image tags in Compose still need verification and digest pinning.

For moving a real site, pause writes and jobs, take a final encrypted database/files/site-configuration backup, restore on the destination with the matching application release and encryption key, test it, then transfer the tunnel connection. Do not run tunnel replicas against independent copies of the database. Git alone does not carry site data.

## Local machine issue at interruption

Docker Desktop's backend failed to start on the previous Windows machine with an inaccessible Unix socket/reparse-point error for `%LOCALAPPDATA%\Docker\run\sailor-ingest.sock` (Windows error 1920). CLI restart and stale-socket cleanup attempts did not fix it. Its old runtime directory was preserved as `%LOCALAPPDATA%\Docker\run-recovery-20261021`; containers/database volumes were not removed. Further repair of that Windows installation is not required to continue on another machine with a working engine.

## Suggested prompt for the next agent

> Continue AI Coach v2 from the ai-coach-v2 branch of https://github.com/dipeshonnet/training. Read HANDOFF.md and deploy/versions.json first. This is an unfinished checkpoint, not a deployed release. Keep stable LMS v2.66.0, Frappe v16.52.0 and the pinned Payments version-16 revision. Run the existing pure rules tests and custom Vue build, then fix the missing LMS bridge patch and Docker/Frappe bootstrap. Finish the feature, permission, completion, migration, backup and acceptance gates listed in HANDOFF.md. Commit and push tested milestones. Configure training.everydayai.work through Cloudflare only after local integration and access-control checks pass. Keep credentials and real training data outside Git; do not publish a verified release tag until its gates pass.
