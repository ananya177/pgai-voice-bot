# Security

## Secrets

Never commit `.env`, `private.key`, PEM files, API tokens, or JWTs. The included `.gitignore` excludes common secret files. If a private key was ever uploaded, emailed, pasted into a public system, or committed, revoke it and generate a new one.

## Phone-number safety

`config.py` hard-codes the official assessment number and validates it immediately before every outbound call. Editing `.env` to another target is not sufficient to bypass the check.

## Recording safety

The recording downloader requires HTTPS and accepts only Vonage/Nexmo hostnames. Keep recordings limited to the challenge's test conversations. Do not use real patient names, dates of birth, member IDs, prescriptions, or other protected health information.

## Public webhook limitation

A Cloudflare Quick Tunnel makes the Flask routes publicly reachable while the server is running. Use it only for development, stop it after testing, and do not expose unrelated local services through the same tunnel.
