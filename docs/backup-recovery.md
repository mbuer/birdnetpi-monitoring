# Backup and Recovery

## Goal

Keep BirdNET recovery simple and consistent with the AI Nexus Home Lab pattern.

The recovery chain uses two complementary layers:

1. validated PostgreSQL logical dumps inside `ubuntu-infra`
2. Proxmox VM backups stored on external Proxmox backup storage

## Intended backup flow

```text
Proxmox vzdump backup-start
        |
        v
QEMU Guest Agent
        |
        v
runuser -> infra
        |
        v
BirdNET repository -> make backup
        |
        v
validated PostgreSQL dump staged inside ubuntu-infra
        |
        v
Proxmox captures ubuntu-infra VM
        |
        v
external Proxmox backup storage
```

The hook deliberately aborts the VM backup if the logical PostgreSQL backup fails.

The existing daily PostgreSQL timer remains useful for short-term local recovery. The Proxmox flow adds the durable off-VM copy without mounting external backup storage into `ubuntu-infra`.

## Repository entry points

Create and validate a fresh logical dump:

```bash
make backup
```

Test the newest dump by restoring it into a temporary database inside the existing PostgreSQL container:

```bash
make restore-test
```

The restore test does not overwrite the production `birdnet` database.

## Proxmox hook

Template:

```text
proxmox/vzdump-ubuntu-infra-hook.pl
```

Install a customized copy on the Proxmox host and set:

- the `ubuntu-infra` VM ID
- the non-root guest admin user
- the BirdNET repository path inside the guest

Do not commit the customized production copy.

The workflow requires the QEMU Guest Agent to be installed/running in `ubuntu-infra` and enabled for that VM in Proxmox.

## Recovery model

For a full host/VM loss:

```text
restore Proxmox VM backup
        |
        v
ubuntu-infra returns with staged PostgreSQL dump
        |
        v
verify PostgreSQL and BirdNET services
```

For database-only recovery, use a validated logical dump and follow the database recovery notes before resuming ingestion.

A backup policy is considered tested only after `make restore-test` succeeds.
