# Alloy setup

Grafana Alloy runs on the BirdNET Pi and forwards operational logs to Loki.

The current Home Lab configuration deliberately dual-writes to:

- Grafana Cloud Loki
- local Loki on `ubuntu-infra` (`192.168.1.137:3100`)

This keeps the Cloud path available while the local observability stack is being proven stable.

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

`alloy/config.alloy` is a deployable sample with credential placeholders. Do not commit real Grafana Cloud credentials.

## Install or refresh the configuration

Install Grafana Alloy using the official Grafana package instructions, then from the repository root:

```bash
sudo mkdir -p /etc/alloy
sudo cp alloy/config.alloy /etc/alloy/config.alloy
sudo cp alloy/default-alloy /etc/default/alloy
```

Edit `/etc/alloy/config.alloy` and replace:

```text
GRAFANA_CLOUD_USERNAME
GRAFANA_CLOUD_PASSWORD
```

with the runtime Grafana Cloud credentials.

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

Both processed BirdNET logs and weather logs are forwarded to Cloud and local Loki.

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

Verify both destinations rather than assuming a healthy Alloy service proves end-to-end delivery.

Useful local Grafana/Loki queries include:

```logql
{unit="birdnet_analysis.service"}
```

```logql
{job="weather"}
```

Grafana Cloud can be checked with the equivalent log queries against its Loki datasource.

## Migration rule

Do not remove the Grafana Cloud output merely because local Loki is reachable. Retire the Cloud path only after the local Loki storage, Grafana dashboards, and operational history have been observed long enough to provide confidence in the replacement.
