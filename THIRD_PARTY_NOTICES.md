# THIRD_PARTY_NOTICES

Status: release-ready documentation baseline.
Last updated: 2026-04-30

## Scope
This repository uses Python dependencies declared in requirements.txt. Dependencies are installed from package indexes at deploy time and are not vendored into this repository.

## Python Dependencies (requirements.txt)

- fastapi==0.116.1
- uvicorn[standard]==0.35.0
- sqlalchemy==2.0.43
- psycopg[binary]==3.2.9
- python-dateutil==2.9.0.post0
- pydantic-settings==2.10.1
- email-validator==2.2.0
- google-api-python-client==2.176.0
- google-auth==2.40.3
- google-auth-httplib2==0.2.0

## Dependency License Matrix

| Dependency | License (as declared by upstream) | Source |
|---|---|---|
| fastapi | MIT | https://pypi.org/project/fastapi/ |
| uvicorn[standard] | BSD (3-Clause) | https://pypi.org/project/uvicorn/ |
| sqlalchemy | MIT | https://pypi.org/project/SQLAlchemy/ |
| psycopg[binary] | LGPL-3.0-only | https://pypi.org/project/psycopg/#data |
| python-dateutil | BSD-3-Clause or Apache-2.0 (dual model; see upstream wording) | https://pypi.org/project/python-dateutil/ |
| pydantic-settings | MIT | https://github.com/pydantic/pydantic-settings/blob/main/LICENSE |
| email-validator | Unlicense (formerly CC0 for older releases) | https://pypi.org/project/email-validator/ |
| google-api-python-client | Apache-2.0 | https://pypi.org/project/google-api-python-client/#data |
| google-auth | Apache-2.0 | https://pypi.org/project/google-auth/ |
| google-auth-httplib2 | Apache-2.0 | https://pypi.org/project/google-auth-httplib2/ |

Notes:

- `google-auth-httplib2` is marked as deprecated upstream; plan migration where possible.
- Dependency licenses can change across versions; always re-check on version bumps.

## License Handling

- Project license: MIT (see LICENSE).
- Each dependency is subject to its own upstream license.
- Keep the project-level license compatible with dependency licenses.
- For release artifacts, include dependency notices when required by upstream terms.

## Verification Checklist Before Public Switch

- Ensure no dependency has a restrictive/non-compatible license for intended distribution model.
- Keep a private SBOM/license export per release.
- Re-run this check whenever requirements.txt changes.

## Internal Evidence (Optional)

Store these privately (not in git):

- Dependency license export per release.
- SBOM snapshot per release.

## Maintainer Note

This file is a legal/compliance helper, not legal advice.
