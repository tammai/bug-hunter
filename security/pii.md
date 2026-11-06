# Personal data (PII) checklist

## What counts as personal data

Anything that identifies a person or is about an identifiable person:
- **Contact:** name, email, phone, postal address.
- **Identity:** national id (passport, ID card, SSN, tax number), date of birth, photo, government documents.
- **Financial:** payment card numbers, bank accounts, transaction history.
- **Location:** GPS coordinates, precise addresses, IP addresses tied to a user, device ids.
- **Sensitive categories:** health and medical data, biometrics, religion, ethnicity, sexual orientation, political views.
- **Credentials:** passwords, security answers, tokens (also covered by the secrets checks).

The owner's `policy.md` may add fields specific to the business.

## The five categories to check

- **`pii-logged`:** personal data written to logs, debug output, analytics events or error tracking breadcrumbs: whole request bodies, user objects, emails in log lines, card numbers in payment errors. CWE-532.
- **`pii-exposed`:** an API returns more than the caller needs: full user records with password hashes, other users' emails in a list, internal notes, ids that enable enumeration. The ORM entity serialized as-is is the usual cause. CWE-359.
- **`pii-third-party`:** personal data sent to an outside service (email, SMS, analytics, CRM, AI APIs, error tracking, CDNs) beyond what that service needs, or without the user's knowledge. Cite the SDK call. CWE-359.
- **`pii-storage`:** sensitive fields (national id, health, payment card, precise location) stored in plain text where field-level encryption or tokenization is expected; full card numbers stored at all (PCI); backups or exports in plain files. CWE-312.
- **`pii-retention`:** no way to delete a user's data (no delete endpoint or job, soft delete that keeps everything, data copied into logs, search indexes or third parties with no deletion path), or data kept with no expiry where it should have one. CWE-359.

## The inventory

For each personal field you meet, record one inventory line: where it's defined, and where it's logged, returned, sent, stored (and whether encrypted) and deleted, each with a `path:line`.
