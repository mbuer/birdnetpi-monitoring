#!/usr/bin/perl -w
use strict;

# ubuntu-infra vzdump hook template.
# Customize these values only in the installed Proxmox copy.
# Keep live VM identifiers and environment details out of the public repository.
my $UBUNTU_INFRA_VMID = 'REPLACE_WITH_VMID';
my $UBUNTU_INFRA_USER = 'REPLACE_WITH_ADMIN_USER';
my $UBUNTU_INFRA_REPO = '/path/to/birdnetpi-monitoring';

my $phase = shift;

if ($phase eq 'backup-start') {
    my $mode = shift;
    my $vmid = shift;

    exit(0) unless defined($vmid) && $vmid eq $UBUNTU_INFRA_VMID;

    my @cmd = (
        '/usr/sbin/qm', 'guest', 'exec', $UBUNTU_INFRA_VMID, '--',
        '/usr/sbin/runuser', '-u', $UBUNTU_INFRA_USER, '--',
        '/bin/bash', '-lc',
        "cd '$UBUNTU_INFRA_REPO' && make backup"
    );

    print "BIRDNET-HOOK: creating fresh PostgreSQL logical backup before VM backup\n";

    system(@cmd) == 0
        or die "BIRDNET-HOOK: logical backup failed; aborting VM backup\n";

    print "BIRDNET-HOOK: logical backup completed successfully\n";
}

exit(0);
