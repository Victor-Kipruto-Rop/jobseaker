# Gmail integration

JobSeeker supports an optional, read-only Gmail connection.

## Google Cloud setup

1. Create or select a Google Cloud project.
2. Enable the Gmail API.
3. Configure an OAuth consent screen.
4. Create an OAuth client of type Web application.
5. Add this exact authorized redirect URI:

   http://localhost:8000/api/v1/integrations/gmail/callback

6. Save the downloaded OAuth client JSON outside the repository.

For local Docker, place the file at:

   secrets/google-oauth-client.json

Set these values in .env:

   GMAIL_ENABLED=true
   GMAIL_CLIENT_SECRET_FILE=/run/secrets/google-oauth-client.json
   GMAIL_REDIRECT_URI=http://localhost:8000/api/v1/integrations/gmail/callback
   APP_SECRET_KEY=<a stable random secret of at least 32 characters>

The Compose file mounts the local secrets directory read-only into the API container.

## User workflow

1. Sign in to JobSeeker.
2. Open the Recruiter Inbox.
3. Select Connect Gmail.
4. Approve the gmail.readonly permission in Google.
5. Return to JobSeeker and synchronize messages.

The integration reads message metadata and snippets for job-related mail. It does not read full message bodies and does not send, mark as read, archive, modify, or delete email.

OAuth credentials are encrypted in the database. The encryption key is derived from APP_SECRET_KEY. Keep that secret stable and backed up.

## Limitations

- Gmail sync is user-initiated. Scheduled mailbox sync is not enabled yet.
- Classification is deterministic keyword-based and must be reviewed.
- Gmail messages are not automatically linked to applications or recruiter records yet.
- Disconnect removes the locally stored connection and message metadata. Also revoke JobSeeker access in your Google Account permissions.
