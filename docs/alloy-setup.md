# Alloy setup

Grafana Alloy runs on the BirdNET Pi and forwards operational logs to Loki.

The current Home Lab configuration forwards operational logs only to local Loki on `INFRA_HOST`.

Grafana Cloud Loki was retired on 2026-09-26 after local Loki delivery was validated for both BirdNET journal data and weather logs.

## Runtime files

```text
/etc/alloy/config.alloy
/etc/default/alloy
/var/lib/alloy/data
```

Repository copies:

```text
alloy/config.alloy
alloy/default-alloy
```

`alloy/config.alloy` is the deployable local-only reference configuration. No Cloud Loki credentials are required.

## Install or refresh the configuration

Install Grafana Alloy using the supported package for the Pi OS. Then use the canonical Pi deployment workflow:

```bash
make pi-bootstrap
```

The bootstrap installs the committed Alloy configuration and systemd environment override while keeping the real Loki endpoint outside Git.

The local Loki endpoint does not currently use authentication inside the Home Lab:

```text
${BIRDNET_LOKI_URL}/loki/api/v1/push
```

Set `BIRDNET_LOKI_URL` in the installed runtime environment. The live address must not be committed.

## What Alloy collects

The committed configuration collects:

- systemd journal events
- BirdNET analysis logs, including parsed species/confidence labels
- `/var/log/weather/weather.log`

Both processed BirdNET logs and weather logs are forwarded to local Loki.

## Validate before restart

The bootstrap validates the committed Alloy configuration before enabling/restarting the service. For manual troubleshooting, use `alloy validate` with the runtime environment loaded before replacing a known-good configuration.

## Verify

```bash
systemctl status alloy --no-pager
journalctl -u alloy -n 50 --no-pager
```

Run `make pi-verify` as the primary acceptance check. It verifies the service, Git/live config match, Loki readiness, and recent BirdNET/weather delivery. A healthy Alloy process by itself is not enough.

Useful local Grafana/Loki queries include:

```logql
{unit="birdnet_analysis.service"}
```

```logql
{job="weather"}
```

## Retired Cloud path

The former Grafana Cloud Loki output is intentionally absent from the active configuration. Reintroducing an external log destination is an architectural change and should be reviewed explicitly rather than restored from an old backup or stale Pi working copy.
