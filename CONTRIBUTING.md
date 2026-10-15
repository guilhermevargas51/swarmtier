# Contributing

Thanks for helping. The rules are short.

## Run the checks

```
pip install pytest
pytest -q
python scripts/pii_scan.py --self-test && python scripts/pii_scan.py
```

CI runs the same two commands on Python 3.10 and 3.12. Both must pass.

## No personal data

This repo is public. Nothing that identifies a person may enter it: names, usernames, e-mails, machine paths,
employers, API keys, tokens, `.env` files, or screenshots that show any of them.
`scripts/pii_scan.py` checks for generic patterns. It also reads a private blocklist from the file named in
`SWARMTIER_PII_BLOCKLIST` or from `~/.swarmtier/pii-blocklist.txt`; that file stays on your machine and is never committed.
If the scan flags something, fix the content. Do not edit the scanner to make it pass.

## Numbers

Cost claims are given as proportions or taken from a cited public source with a date. Do not add dollar figures
from your own usage. If you measure something new, describe the method next to the number.

## Pull requests

- One PR, one change. A bug fix does not carry a refactor.
- Add or update a test when behaviour changes.
- Hooks must never break a session: bad input exits 0. Only `require-effort` blocks, on purpose.
- Keep docs in English; `README.pt-BR.md` follows `README.md`.

## Reporting bugs

Open an issue with what you ran, what you expected and what happened. For security problems, see [SECURITY.md](SECURITY.md) instead.
