# GitOps for ExecutaLlama

This project supports GitOps workflows for both code and Tailscale ACLs.

## CI/CD (GitHub Actions)
- On every push to `master`, the code is built and deployed to your Pi (or server) using SSH.
- Configure your Pi's SSH host, user, and private key as GitHub repo secrets: `PI_HOST`, `PI_USER`, `PI_KEY`.
- The workflow will rsync code and restart the service.

## Tailscale ACLs
- Store your ACL config in `tailscale-acl.json`.
- Edit in Git, review via PR, and copy-paste into the Tailscale admin console for enforcement.
- (Enterprise: automate ACL sync with Tailscale API.)

## How to use
1. Fork or clone this repo.
2. Set up GitHub repo secrets for deployment.
3. Edit code or ACLs, push to master, and your Pi will auto-update.
4. Use the dashboard or CLI as usual.
