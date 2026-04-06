Installer smoke tests for the public SDK installer.

These tests build distro-specific Docker images and run:

```bash
curl -SsLf https://mwm.datallog.com/install.sh | bash
```

Covered cases:

- `ubuntu-26.04`: native Ubuntu 26.04 container
- `linuxmint`: Ubuntu 26.04 container with `/etc/os-release` overridden to trigger the installer's Mint branch
- `fedora`: Fedora container, also checks that the installer writes `podman` into `settings.json`
- `arch`: Arch Linux container

Run all cases locally with Docker:

```bash
bash tests/install-smoke/run-all.sh
```

Run all cases locally with Podman:

```bash
CONTAINER_CLI=podman bash tests/install-smoke/run-all.sh
```
