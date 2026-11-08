# Windows setup checks

Complete [HOST_SETUP.md](../HOST_SETUP.md) first. These notes cover common fresh
Windows 11 x64 installations; they are not instructions to turn security off.

## Python and the py command

Use the [python.org Windows download](https://www.python.org/downloads/windows/)
for the classic installer or official Python install manager. With the classic
installer, include the Python launcher. With the manager, run `py install 3.14`.
The official manager can also be obtained through Microsoft's Store; the Store
itself is not the problem. An older per-version Store installation may expose
different commands, so confirm the required launcher explicitly:

```powershell
py -3.14 --version
```

Choose standard **CPython 3.14 x64**, not 32-bit, native ARM64 or **3.14t/free-
threaded**. The lock contains standard cp314 Windows x64 wheels, not cp314t
wheels. Setup/Upgrade runs `check_python.py` before pip and explains a mismatch.
Windows on ARM using x64 emulation remains untested. If py is not recognized,
finish/repair the official install and reopen the terminal; don't substitute an
arbitrary Python executable or remove the wheel/hash constraints.

Reference: [Python's Windows guide](https://docs.python.org/3.14/using/windows.html).

## Home network and firewall

On a **trusted home LAN only**, open Settings → Network & internet → Wi-Fi →
your connected network → Network profile type → **Private**. Ethernet has an
equivalent connected-network properties page. Keep hotel, school/shared and
coffee-shop networks Public; don't reclassify them just to make discovery work.

When Windows asks to allow the host's Python, allow **Private networks only**.
Some Windows versions show a different prompt; inspect the host Python entry in
Windows Security → Firewall & network protection → Allow an app through firewall,
leaving Public unchecked. Keep the firewall enabled. Don't approve every Python
installation or add broad Public-network rules. The app uses TCP 48152/48153
and UDP 48154 for paired Local audio/control/discovery; Setup does not forward
router ports or enable UPnP. Remote-only Funnel uses loopback instead of LAN.

References: [network profiles](https://support.microsoft.com/en-us/windows/experience/connectivity-networking/essential-network-settings-and-tasks-in-windows)
and [firewall protection](https://support.microsoft.com/en-us/windows/security/firewall-and-network-protection-in-the-windows-security-app).

## Download flag, SmartScreen and Smart App Control

If you trust the expected project's release, right-click the downloaded ZIP →
Properties → **Unblock** → Apply when available, **before** Extract All. Archive
tools/Windows versions differ in how they propagate the internet-download flag.
Unblocking removes that flag; it does not add a digital signature or establish
that an unknown file is safe. Download from this project's Releases and check
its published checksums; checksums alone do not authenticate a publisher.

The project's custom capture EXE and Opus DLL are currently **unsigned**.
SmartScreen/reputation checks or **Smart App Control** may block the scripts,
`soloist-capture.exe` or `opus.dll` on a fresh PC. ZIP Unblock may not resolve
Smart App Control enforcement. The project has not been tested with that policy
enabled, and it does not promise compatibility with an enforcing policy.

If Windows blocks a component, keep the exact filename/message, open Windows
Security's Protection history and, when applicable, Event Viewer → Applications
and Services Logs → Microsoft → Windows → CodeIntegrity → Operational. Report
only a redacted relevant excerpt via [SUPPORT.md](../SUPPORT.md). Don't post
credentials or account folders. There is no project-supplied per-app exception
or signed build available yet. Use a supported machine/policy or wait for a
properly signed release; do not disable Defender/firewall/Smart App Control as
an installation step, and do not apply broad exclusions.

Signing requires a separate trusted certificate/provider and a release-signing
setup. Rebuilding/checksumming in CI is not code signing or proof of Smart App
Control acceptance. See Microsoft's [developer overview](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/overview)
and [policy test guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/test-your-app-with-smart-app-control).
