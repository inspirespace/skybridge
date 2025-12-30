# Backend Release Readiness Checklist

## Auth & User Experience
- [ ] Sign-up/sign-in flow validated for new users.
- [ ] Clear error messaging on invalid credentials.
- [ ] Job progress UI reflects state changes and provides per-step counts.

## Migration Reliability
- [ ] Review summary shows flight count, hours, and per-flight details.
- [ ] Import report shows imported/skipped/failed counts.
- [ ] Retry logic confirmed for transient API failures.

## Security & Compliance
- [ ] Credential handling verified (no persistence).
- [ ] TLS enforced end-to-end.
- [ ] Logs scrub sensitive fields.

## Operations
- [ ] Runbook followed successfully for a test migration.
- [ ] Maintenance checklist reviewed and scheduled.
- [ ] Alerts configured (budget, error rate, latency).

## Cost Controls
- [ ] Quotas enforced per user.
- [ ] TTL policies validated for artifacts and job metadata.
