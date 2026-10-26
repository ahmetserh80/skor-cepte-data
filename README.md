# Skor Cepte — public data collector

Prepared deployment target: `ahmetserh80/skor-cepte-data` (a new public repository).
This directory is a reviewable package. It is not an active deployment and its
workflow does not run inside the private iOS repository.

The package contains the official-source reader, validation, province identities,
notification text/sender and automated checks. It contains no iOS application,
screens, account credentials, signing keys, device records or captured snapshots.
Runtime data and keys must never be committed to this repository.

## Free operating model

- Standard `ubuntu-24.04` Actions runners in a public repository: no runner-minute
  charge under GitHub's published current pricing.
- No Actions artifact uploads or persistent cache storage.
- cron-job.org's free timer dispatches a scan at `00,15,30,45` each hour.
- GitHub's `07,22,37,52` schedule is a fallback. A source start-time check skips a
  second completed scan for the same quarter-hour; a concurrency group serializes
  runs. Both providers can be delayed, so these times are targets, not an SLA.
- Each scan has a 14-minute job timeout and three concurrent province readers.
- The private account's existing zero-dollar Actions spending limit stays enabled.

## Activation checklist

1. Obtain permission to publish precisely this collector package. Create the new
   public repository; keep the iOS repository private. Record its actual GitHub
   repository ID; do not infer it from its name.
2. Deploy the source-failure preservation update to the data service, then configure
   its OIDC verifier for that exact repository ID,
   owner ID `306619172`, `refs/heads/main`, workflow
   `.github/workflows/skor-live-data.yml`, and its existing exact audience. Forks,
   PRs, other branches and other repositories must remain unauthorized. Verify
   those negative cases before publishing the service change.
3. Provision `APNS_KEY_ID`, `APNS_KEY_P8_BASE64`, and `APPLE_TEAM_ID` as encrypted
   Actions secrets in the new repository through a separately authorized setup.
   Never put their values in files, logs, comments or cron-job.org. The workflow
   validates the APNs configuration before beginning a source scan.
4. Create/sign in to the owner's free cron-job.org account. Use a fine-grained
   GitHub token restricted to the new collector repository with Actions write
   and the automatically required Metadata read permission. Actions write can
   also manage runs, so it is broader than dispatch alone. Do not grant code,
   signing, billing or other-repository access to the timer. Set an expiry and
   plan its renewal; never use an untracked perpetual token.
5. Configure the job described below, then run a test dispatch. Confirm a full
   successful scan, public app-shaped data download and APNs delivery result.
6. Enable the timer. Verify two consecutive automatic executions, their GitHub
   run IDs, the app-visible data and authentic source start timestamps. Apple
   accepting a push does not prove a phone displayed it.
7. Only after those checks, disable the old private scheduled collector. Keep a
   deliberate rollback path. Remove the old runner authorization when migration
   is proven. Do not leave two uncoordinated publishers running.

## cron-job.org job

Name: `Skor Cepte — 15 dakika veri yenileme`

Method: `POST`

URL:
`https://api.github.com/repos/ahmetserh80/skor-cepte-data/actions/workflows/skor-live-data.yml/dispatches`

Headers:

```
Accept: application/vnd.github+json
Content-Type: application/json
Authorization: Bearer <repository-scoped Actions token entered securely>
```

Body: `{"ref":"main","inputs":{"force":false}}`

Schedule: every day, every hour, minutes `0,15,30,45`; timezone `Europe/Istanbul`.
The HTTP request only queues the workflow and should return `204` quickly; it does
not wait for the scan. Enable the service's job-failure notification during setup.

## Validation

```
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.mjs
```

The displayed update timestamp is the real source-collection start of a
successful batch. An unavailable source preserves its last verified data and
timestamp. It never receives a fabricated current time. When a runner cannot load a
province's prior record, it sends only its identity and a source-failure marker;
the data service must restore its own published record. It never trusts a bundled
older fallback. An unavailable registry stops collection. The current iPhone app reads the
same `last_success_at` field, so no binary update is required for this timestamp.

The delivery check explicitly allows server-preserved records bearing a valid
source-failure marker, up to the service's 30-day retention limit. This does not
advance their clock or mark them fresh. A province outage must not block delivery
of other provinces' newly published events. Release-bundle validation remains
strict by default and rejects snapshots older than six hours.

## Source incidents and email noise

Read operations retry once after two seconds only for timeouts, connection
resets and HTTP 502/503/504/522/524. Access denials, rate limits, TLS errors,
unexpected redirects and data validation failures are never bypassed or retried.
The existing request spacing, validation and 14-minute total limit remain.

Isolated transient source outages produce a warning and preserve the original
snapshot and timestamp. If the same province stays unavailable for 45 minutes,
the first such run fails to raise a GitHub alert. Validation/feed failures and
outages affecting at least four provinces alert immediately. Incident state is
saved in the existing published registry, so repeated source incidents do not
send a new failed-run email on every scan. A successful source read clears that
incident and permits a new alert for a later outage. Recovery and ongoing source
status remain visible in the run logs/summary, rather than a separate email.

This does not mute failures of tests, credentials, scheduling, publication,
public-feed verification or push delivery; those still fail normally. No GitHub
account notification settings are changed, and no paid storage is introduced.

## References

- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://cron-job.org/en/faq/
- https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event


## App Store çıkışı öncesi yapılacak: bağımsız Telegram alarmı

26.10.2026 kullanıcı kararı: Skor Cepte Telegram sağlık alarmı şimdi kurulmayacak;
App Store yayınına hazırlanırken kurulacak. Son başarılı veri alımından itibaren
bir saat aşılırsa etkilenen il, son başarılı tarih-saat ve hata nedeni ile tek
alarm; sorun sürerse üç saat sonra hatırlatma; düzelince tek toparlanma mesajı.
Denetim, veri toplayıcıdan bağımsız çalışmalı ve tarama hiç tetiklenmediğinde de
alarm verebilmeli. Bu, merkezi yedekleme için kullanılan Telegram alarmından
ayrı bir takip kapsamıdır. Henüz kurulmuş/etkin değildir.
