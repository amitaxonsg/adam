# Deploying the secure Adam questionnaire submission backend

**GitHub Pages cannot execute PHP or persist form submissions.** These backend files are deployment source only; uploading them to GitHub does NOT make saving work.

## Requirements
- PHP 8.1+ and PDO_SQLITE on your own PHP-enabled hosting.
- HTTPS endpoint e.g. `https://forms.yourcompany.com/adam-api/index.php`.
- A writable private SQLite database location **outside public_html**.
- Environment configuration:
  - `ADAM_DB_PATH=/home/USER/adam_private/answers.sqlite` (absolute path; create directory with restrictive permissions).
  - `ADAM_ALLOWED_ORIGIN=https://amitaxonsg.github.io`
  - `ADAM_ADMIN_TOKEN=<generated-cryptographically-random-token-32+-characters>` (never commit this token).
  - `ADAM_IP_SALT=<different-random-secret>`.

## Steps
1. Deploy `backend/index.php` to `https://forms.yourcompany.com/adam-api/index.php` under a PHP site. Do **not** serve SQLite or the secrets publicly.
2. Enable PHP/PDO_SQLITE, environment variables, TLS, backups, HTTPS-only access and server log monitoring.
3. Edit `config.js` in the GitHub repo to set `window.ADAM_API_ENDPOINT` to your real, tested HTTPS API endpoint.
4. On the live form, complete one sample and click **Submit securely to Axon server**. You should receive a submission reference ID. A successful response is HTTP 201 with `saved:true`. If not, no server save has occurred.
5. Confirm the saved submission using an admin-only API request with `Authorization: Bearer <token>` and `GET /index.php?id=<submission_id>`. Never put the admin token in a browser URL or public site.
6. Retrieve all recent records via authenticated `GET /index.php`; back up the private database securely. Ensure only authorized staff handle personal information.
7. Independently test PDF: complete representative answers, click **Print / Save PDF**, select PDF in the browser dialog, open the output and check for all sections/answers.

## API contract
- `POST` JSON body: `{schema, respondent, responseDate, general, dependencies, answers}` + honeypot `website`. No browser authentication required for customer submissions; origin restriction, size limits, validation and rate limiting mitigate basic abuse but do not prevent all spam.
- `GET` admin Bearer token, optional `?id=`.
- The questionnaire still offers JSON/text downloads as fallback when the API is unavailable.

**Important:** Do not request or retain customer passwords, bank card details, API secrets or private customer rosters in this questionnaire. Treat submitted answers as potentially confidential, apply a defined retention/deletion policy, and confirm legal/privacy obligations with the client.

## Hosting status
At commit time, there is no configured PHP deployment or confirmed backend endpoint. **Server-side saving is NOT yet active.**
