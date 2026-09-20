# Public web deployment contract

Use the host's existing reverse proxy and certificate tooling. A public deployment is complete only after client-side verification of DNS, HTTPS/certificate hostname, expected content, denied access to dotfiles/secrets/VCS/backups, and no direct public access to the application or development port.

For static content, serve only the built output directory. For an application, proxy to a loopback upstream and preserve required forwarding/websocket headers. Do not invent a new proxy stack when the host already has one.

Inspect DNS, active listeners, existing virtual hosts, and certificate state before proposing mutations. Show the exact proposed config and obtain authorization required by the active workflow before DNS, package, firewall, proxy reload, or certificate changes. Validate configuration syntax before reload and retain the previous config for rollback.

Certificate issuance requires working public DNS and ports 80/443. Diagnose NXDOMAIN or wrong-address failures at DNS rather than repeatedly invoking the issuer.
