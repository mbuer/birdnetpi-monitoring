# Alloy setup

Grafana Alloy runs on the BirdNET Pi and forwards operational logs to Loki.

The current Home Lab configuration forwards operational logs only to local Loki on `ubuntu-infra` (`192.168.1.137:3100`).

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

Install Grafana Alloy using the official Grafana package instructions, then from the repository root:

```bash
sudo mkdir -p /etc/alloy
sudo cp alloy/config.alloy /etc/alloy/config.alloy
sudo cp alloy/default-alloy /etc/default/alloy
```

The local Loki endpoint does not currently use authentication inside the Home Lab:

```text
http://192.168.1.137:3100/loki/api/v1/push
```

If the infrastructure VM address changes, update this endpoint deliberately rather than treating the current address as a universal default.

## What Alloy collects

The committed configuration collects:

- systemd journal events
- BirdNET analysis logs, including parsed species/confidence labels
- `/var/log/weather/weather.log`

Both processed BirdNET logs and weather logs are forwarded to local Loki.

## Validate before restart

When changing the installed configuration, validate it before replacing a known-good setup if the installed Alloy version supports configuration validation.

At minimum, preserve the existing runtime file before a substantial edit:

```bash
sudo cp /etc/alloy/config.alloy /etc/alloy/config.alloy.bak
```

Then restart:

```bash
sudo systemctl enable alloy
sudo systemctl restart alloy
```

## Verify

```bash
systemctl status alloy --no-pager
journalctl -u alloy -n 50 --no-pager
```

Verify local Loki delivery rather than assuming a healthy Alloy service proves end-to-end delivery.

Useful local Grafana/Loki queries include:

```logql
{unit="birdnet_analysis.service"}
```

```logql
{job="weather"}
```

## Retired Cloud path

The former Grafana Cloud Loki output is intentionally absent from the active configuration. Reintroducing an external log destination is an architectural change and should be reviewed explicitly rather than restored from an old backup or stale Pi working copy.
