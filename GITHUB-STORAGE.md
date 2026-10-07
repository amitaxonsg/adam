# Adam questionnaire — GitHub storage and file uploads

## What is live on GitHub Pages
- The questionnaire at https://amitaxonsg.github.io/adam/ is a **static website**.
- It can export complete answers and supporting documents in **one JSON file**. Documents are base64-encoded within `attachments[]`, with name, MIME type and size.
- PDF: **Print / Save PDF** via the visitor's browser. It is a printout of questions/answers, not a server-generated PDF.
- TXT: readable answer text export; for binary file attachments use the JSON export.
- JSON import lets Axon reload previously completed answers and attachment metadata.
- Current file limits: 5 MB per file, 15 MB total before base64 overhead.
- **Automatic server or GitHub saving is not live.** A successful download does not imply server-side saving.

## Store responses only in GitHub (recommended private repository)
1. Create a **separate PRIVATE GitHub repository**, e.g. `amitaxonsg/adam-private-responses`. Never put submitted customer data into the public `amitaxonsg/adam` repository.
2. Request Adam to click **Download responses (JSON)** and share the file over a secure, agreed channel.
3. Axon uploads each JSON response into the private repository under `submissions/YYYY-MM-DD/<reference>.json`.
4. The attached documents will be inside that JSON. When extracting, base64-decode each attachment back to its source file.
5. Restrict access and apply an agreed deletion/retention policy. A Git repository preserves history, so deleting a file in a later commit may not fully remove personal data from history.
6. For an automated **Submit** button, deploy a separate HTTPS endpoint with a server-side GitHub App or fine-grained token restricted to the private repository. Keep the token in server-side secrets only, never in JavaScript or public Git. Include anti-spam protection, input and file validation, logging controls and private repository enforcement.

## Domain, email, supplier and shipment questions
The questionnaire also asks for domain registrar, DNS/Cloudflare manager, business email provider, transactional email setup, supplier names + API docs, courier/shipping provider names + API docs, customer tracking preferences, artwork requirements, production machinery, factory software, and other client ideas.

## Confidentiality
Do not enter API keys, bank credentials, private customer rosters or passwords. Uploaded documents should be carefully reviewed before storage.
