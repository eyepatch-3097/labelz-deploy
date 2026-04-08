Security Policy for Labelz

Overview

Labelz is committed to ensuring the security of our users and their data. This document outlines our policy for reporting vulnerabilities, our supported versions, and our general security posture regarding the technologies used in this repository.

Supported Versions

We actively provide security updates for the following versions of Labelz:

Version

Supported

Latest

:white_check_mark:

< 1.0

:x:

Reporting a Vulnerability

Please do not report security vulnerabilities through public GitHub issues.

If you discover a security vulnerability, please report it privately to ensure the safety of our users.

Email: [Insert Security Contact Email]

Response Time: You can expect an acknowledgment within 48 hours.

Process: We will investigate the report, provide a timeline for a fix, and coordinate a public disclosure once the patch is released.

Tech Stack Security Implementation

Based on our requirements.txt, we implement the following security measures:

1. Framework & Data Validation

Django 6.0: We leverage built-in protections against CSRF, XSS, and SQL Injection.

Pydantic (v2.12): Used for strict data parsing and validation to prevent malformed data from reaching core logic.

Bleach (v6.3): Utilized to sanitize any user-provided HTML to prevent Cross-Site Scripting (XSS).

2. Financial & Third-Party Integrations

Razorpay: All payment integrations follow PCI-DSS compliance standards. API keys must strictly be managed via environment variables (python-dotenv).

OpenAI & PostHog: Data sent to third-party providers is minimized to what is strictly necessary for functionality and telemetry.

3. File & Document Generation

ReportLab & Python-Barcode: Since we generate dynamic PDF and barcode content, we ensure that input data is sanitized before being passed to these rendering engines to prevent document injection attacks.

4. Infrastructure

WhiteNoise: Configured for secure static file serving with appropriate cache headers.

Psycopg2 & PGVector: Database interactions are handled via the Django ORM to prevent SQL injection.

Security Best Practices for Contributors

Never Commit Secrets: Ensure .env files, API keys (Razorpay, OpenAI, Resend), and Django SECRET_KEY are never committed to the repository.

Environment Configuration: Use DEBUG=False in any environment accessible via the public internet.

Dependency Updates: We use tools like pip-audit to monitor for vulnerabilities in the dependencies listed in requirements.txt. Contributors should flag any outdated or vulnerable packages.

Least Privilege: Ensure database users and API keys have the minimum permissions required to function.

Disclosure Policy

We follow a coordinated disclosure model:

Reporter private disclosure.

Investigation and fix development.

Patch release and version bump.

Public announcement and attribution to the reporter.
