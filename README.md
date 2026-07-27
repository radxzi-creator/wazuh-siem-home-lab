# Wazuh SIEM Home Lab — Detection & Log Analysis

A self-built SIEM environment using Wazuh, VirtualBox, and Ubuntu Server, built to gain hands-on experience with log monitoring, agent-based detection, and file integrity monitoring (FIM) — skills that complement my existing [AWS SOC Detection Pipeline](#) project.

**Status: Manager and agent deployed and actively connected.** File Integrity Monitoring and alert testing in progress.

---

## Overview

This lab deploys the full Wazuh stack (indexer, manager, dashboard) on one Ubuntu Server VM, plus a second Ubuntu Server VM running the Wazuh agent, registered and reporting back to the manager.

**Stack:**
- VirtualBox (host hypervisor)
- Ubuntu Server 22.04.5 LTS (manager VM + agent VM)
- Wazuh 4.14.6 (indexer + manager + dashboard on the manager node; agent package on the second node)

**Host specs:** Intel i5-13420H, 8GB RAM — a genuinely resource-constrained environment for running two VMs simultaneously, which shaped several of the decisions below.

---

## Architecture

- Host machine runs VirtualBox with a bridged/NAT network setup
- `wazuh-manager` VM (Ubuntu Server 22.04, 4GB RAM) runs the indexer, manager, and dashboard
- `wazuh-agent-01` VM (Ubuntu Server 22.04, 1.5-2GB RAM) runs the Wazuh agent, registered against the manager
- Dashboard accessed via HTTPS (port 443) from the host browser
- Agent connects outbound to the manager over the local network
<img width="397" height="153" alt="Screenshot 2026-07-19 205809" src="https://github.com/user-attachments/assets/db1077e0-df2b-424a-a1bf-10796cc6a264" />
---

## Day 1 — Manager build

### 1. Initial VM attempt — Ubuntu Desktop

Started with Ubuntu Desktop, which turned out to be the wrong choice for a manager node (heavier, GUI overhead not needed for a headless SIEM component).

**Issue:** Black screen on boot for over an hour.
**Root cause:** Optical drive showed "Empty" — the ISO wasn't actually attached to the VM's storage controller.
**Fix:** Re-attached the ISO under Settings → Storage, confirmed it showed the correct filename before booting again.

**Secondary issue:** Black screen persisted even after fixing the ISO attachment.
**Root cause:** Graphics controller mismatch with newer Ubuntu builds.
**Fix:** Switched Graphics Controller to VMSVGA, bumped video memory to 128MB.
<img width="630" height="497" alt="Screenshot 2026-07-19 210307" src="https://github.com/user-attachments/assets/0a09415a-39dc-4832-b8ec-867ba7514784" />
### 2. RAM constraints under Ubuntu Desktop

**Issue:** Repeated logouts / session crashes while running `apt upgrade`.
**Root cause:** Desktop edition's GUI overhead was too much for an 8GB host.
**Fix:** Switched to Ubuntu **Server** edition — lighter, and the correct choice for a manager node.

### 3. Blocked ISO download — Windows Smart App Control

**Issue:** Direct `.iso` download blocked outright by Windows.
**Root cause:** `.iso` is on Smart App Control's default blocked file-extension list.
**Fix:** Downloaded the official `.torrent` file and used qBittorrent instead — same official Ubuntu release, different delivery path.

<img width="1130" height="372" alt="Screenshot 2026-07-19 210600" src="https://github.com/user-attachments/assets/c2f33616-2264-45c1-b471-6685c0ec7a06" />
### 4. Ubuntu Server install and login

Installed cleanly once the correct ISO was in hand.

### 5. Wazuh install script — silent curl failure

**Issue:** `curl` returned "No such file or directory" with no visible error, using an outdated version path (`4.9` instead of current `4.14`).
**Fix:** Switched to `wget`, which downloaded successfully on the first attempt.

### 6. Hardware requirement check

**Issue:** Installer refused to proceed — system didn't meet the 4GB RAM / 2 CPU minimum (VM was set to 3GB).
**Fix:** Increased Base Memory to 4GB, re-ran the installer.<img width="802" height="588" alt="Screenshot 2026-07-19 211208" src="https://github.com/user-attachments/assets/da2f4c66-c870-4ce5-8f71-3a14d360036a" />
### 7. Successful install

Full stack installed cleanly: indexer → manager → Filebeat → dashboard, with admin credentials generated on completion.

### 8. Post-reboot authentication failure

**Issue:** After an accidental shutdown/restart, dashboard login failed despite correct credentials.
**Diagnosis:** All three services confirmed `active (running)` — ruled out a service failure, pointed to an auth-sync issue.
**Fix:** Reset the admin password using Wazuh's built-in tool:
```bash
sudo bash /usr/share/wazuh-indexer/plugins/opensearch-security/tools/wazuh-passwords-tool.sh -u admin -p 'NewPassword.'
```
(Password policy requires a symbol from a specific set — `. * + ? -` — common symbols like `!` are rejected.)

<img width="1918" height="1031" alt="wazuh dash" src="https://github.com/user-attachments/assets/768921af-574c-4ef1-b374-b8c1467bc805" />
---

## Day 2 — Agent build

### 9. Agent VM install failures — DNS resolution

Built a second VM (`wazuh-agent-01`) for the Wazuh agent. The Ubuntu Server autoinstall **failed four consecutive times**, always at the identical stage: downloading the kernel package (`linux-generic`).

**Diagnosis process:**
- Confirmed disk space was not the issue (`df -h` showed plenty free)
- Suspected resource contention (host showed a kernel `soft lockup` warning while both VMs ran simultaneously) — fully shut down the manager VM to free RAM, retried — **still failed**, ruling out resource contention as the sole cause
- Pulled the actual curtin install log (`/var/log/installer/curtin-install.log`) and found the real error: `Temporary failure resolving 'au.archive.ubuntu.com'` — a **DNS resolution failure**, not a resource or disk issue

**Root cause — the deep one:** `/etc/resolv.conf` inside the install target was a **symlink** to `systemd-resolved`'s stub resolver, which itself couldn't reach a working upstream DNS server. Writing a new DNS server directly to `/etc/resolv.conf` appeared to work but was actually being silently discarded because it was writing through the symlink to a file that gets regenerated.

**Fix:**
```bash
rm /target/etc/resolv.conf
printf 'nameserver 8.8.8.8\n' > /target/etc/resolv.conf
```
Breaking the symlink and replacing it with a real static file let the manual package install succeed, and the autoinstall process completed on its next automated retry.

### 10. Forgotten VM password — GRUB recovery mode

**Issue:** After the install finally completed, forgot the password set during the (failed-then-recovered) autoinstall process.
**Fix:** Booted into GRUB recovery mode → Advanced options → recovery mode → root shell, then:
```bash
mount -o remount,rw /
passwd wazuh-agent-01
```
Reset the password directly, rebooted normally.
<img width="797" height="538" alt="terminal login sucess  wazuh-agent-02" src="https://github.com/user-attachments/assets/7ec60e27-7684-467d-9419-dc55a662d356" />
### 11. Agent installation and registration

With the OS finally stable, installed the Wazuh agent via the official APT repository method:
```bash
wget -O- https://packages.wazuh.com/key/GPG-KEY-WAZUH | sudo gpg --dearmor -o /usr/share/keyrings/wazuh.gpg
echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" | sudo tee /etc/apt/sources.list.d/wazuh.list
sudo apt update
sudo WAZUH_MANAGER='192.168.0.219' apt-get install wazuh-agent -y
sudo systemctl daemon-reload
sudo systemctl enable wazuh-agent
sudo systemctl start wazuh-agent
```
Clean install, no errors — a genuinely smooth step after everything before it.

### 12. Manager service timeout under load

**Issue:** With both VMs running simultaneously to test the connection, the manager service failed to restart (`start operation timed out`) after another password reset.
**Fix:** Waited for host resources to settle, retried `systemctl start wazuh-manager` — succeeded on retry once contention eased.

### 13. Agent showing "disconnected"

**Issue:** Agent appeared registered in the dashboard (correct name, OS, version) but showed status **disconnected**.
**Root cause:** Agent VM had been paused earlier to free host resources, dropping its live connection.
**Fix:**
```bash
sudo systemctl restart wazuh-agent
```
Refreshed the dashboard — status changed to **active**.
<img width="1902" height="332" alt="wazuh agent 01 active" src="https://github.com/user-attachments/assets/4ad9f676-fe95-4f74-80af-e81a24f2dab4" />
---

## Current state

✅ Wazuh manager (indexer + manager + dashboard) running and stable
✅ Wazuh agent installed, registered, and **active**
✅ Manager and agent confirmed communicating over the local network

## What's next

- [ ] Generate real activity on the agent (file changes, package installs) and confirm alerts land in the dashboard
- [ ] Configure and test File Integrity Monitoring (FIM) against `/etc`
- [ ] Document alert screenshots and FIM test results

---

## Key takeaway

This build involved two genuinely hard debugging chains: a boot/graphics/resource saga on the manager, and a symlinked-DNS failure that took four failed install attempts and a deep dive into curtin's install logs to actually diagnose on the agent. Neither was solved by a tutorial — both required reading actual error output, forming a hypothesis, testing it, and being wrong more than once before finding the real cause. That process, not the clean end state, is the actual skill this lab was built to practice.
Day 3 — Detection testing and File Integrity Monitoring

### 14. Agent reconnection after network change

**Issue:** Agent showed "disconnected" after switching networks between sessions (home wifi ↔ phone hotspot), changing the manager's IP each time.
**Fix:** Updated the agent's `ossec.conf` to point at the manager's current IP, restarted the agent service. This recurred multiple times across the session as the network switched.

### 15. Confirmed events flowing end-to-end

Verified real security events — login sessions, sudo command execution, agent start/stop — flowing correctly from agent to manager to dashboard.

<img width="1907" height="1023" alt="Wazuh-agent-01 login activity screenshot" src="https://github.com/user-attachments/assets/195d90c9-a589-4d7c-8365-9a6baff66ede" />


### 16. File Integrity Monitoring — root cause chase

Configured `whodata` mode on the agent for real-time FIM detection (rather than relying on periodic 12-hour scans):
```bash
sudo apt install auditd -y
```
Edited `ossec.conf`:
```xml
<directories whodata="yes">/etc,/usr/bin,/usr/sbin</directories>
```

Despite confirming `whodata` initialized correctly and `auditd` running healthy, test files created in `/etc` produced no alerts across multiple attempts. Checked agent logs, manager logs, archives, and alert files — all came back empty.

**Root cause, eventually found:** the agent's configured manager IP was stale again — the network had changed since the last connectivity fix, silently disconnecting the agent. Every FIM test during this stretch ran against a disconnected agent, which is why nothing appeared no matter how the detection config was tuned. Not a whodata or logging issue at all — a basic connectivity issue hiding underneath a much more complex-looking symptom.

**Fix:** corrected the manager IP in the agent's `ossec.conf`, restarted, confirmed "active" status in the dashboard, then re-ran the test.

**Result — confirmed working:**
<img width="1911" height="1012" alt="Screenshot 2026-07-25 192233 file integrity monitoring" src="https://github.com/user-attachments/assets/aad7ec87-944d-432d-8417-8bf9e1a7a835" />
---

## Current state

✅ Wazuh manager (indexer + manager + dashboard) running and stable
✅ Wazuh agent installed, registered, and active
✅ Real-time event flow confirmed (logins, sudo, command execution)
✅ File Integrity Monitoring configured with `whodata` mode and confirmed working end-to-end

## What's next

- [ ] Expand FIM testing — file modification and deletion events, not just creation
- [ ] Explore additional detection rules (e.g. unauthorized package installs, privilege escalation)
- [ ] Consider a static/fixed IP setup for both VMs to eliminate recurring reconnection issues

---

## Key takeaway

The most valuable lesson from this build wasn't a specific command or config — it was a debugging discipline: when a fix doesn't work despite everything *looking* correctly configured, check the most basic layer first (is it even connected?) before assuming the problem is in the complex thing you just changed. The FIM alert wasn't broken by whodata, auditd, or Wazuh's rule engine — it was broken by a disconnected network cable, in digital form, hiding underneath several layers of correctly-configured software.
[Host Machine - Windows 11]
     |
     | VirtualBox
     |
     +-- [Manager VM] -----------+
     |  Ubuntu Server 22.04      |
     |  RAM: 4GB                |
     |  ┌──────────────────┐    |
     |  │ Wazuh Indexer    │    |
     |  │ Wazuh Manager    │    |
     |  │ Wazuh Dashboard  │    |
     |  └──────────────────┘    |
     |  Ports: 443, 55000, 1514 |
     +--------------------------+
     |         |
     |         | Agent → Manager (1514/tcp)
     |         |
     +-- [Agent VM] -------------+
        Ubuntu Server 22.04      |
        RAM: 1.5-2GB            |
        ┌──────────────────┐    |
        │ Wazuh Agent      │    |
        │ ossec.conf       │    |
        │ MANAGER_IP:      │    |
        │ 192.168.0.219    │    |
        └──────────────────┘    |
        +--------------------------+