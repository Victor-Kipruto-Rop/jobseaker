# Outreach reconciliation report

**Verification date:** 3 November 2026  
**Source files:** `kenya_data_opportunities_contacts.csv`, `outreach_send_log.csv`  
**Gmail account searched:** connected account, read-only inspection  
**Scope:** all 22 historical SACCO contacts previously recorded as contacted.

## Summary

- Organizations in original tracker: **64**
- Tracker records marked Sent: **53**
- Portal/contact-form records: **11**
- Send-log rows: **31**, all with status Sent
- Send-log rows matched to tracker: **31**
- Historical SACCO contacts found in Gmail: **22 of 22**
- Historical messages with Gmail SENT label: **22**
- Historical messages with `Victor_Kipruto_Resume.pdf` attached: **20**
- Historical messages without CV attachment: **2**
- Historical threads with a delivery failure: **1**
- Incoming recruiter/SACCO replies in the 22 inspected threads: **0**

## Exceptions requiring action

### KCB Kencom SACCO

- Recipient: `info@kcbkencomsacco.co.ke`
- Gmail message ID: `1a1a1a3ea168e65f`
- Gmail thread ID: `1a1a1a3e0ed8b694`
- The sent message included `Victor_Kipruto_Resume.pdf`.
- A Gmail Delivery Status Notification (Failure) followed.
- Bounce text: address not found because the recipient domain could not be found.
- Reconciled status: **Bounced**.
- Action: verify the organization's correct official contact route before attempting another message. Do not resend automatically.

### Acumen DT SACCO

- Recipient: `info@acumensacco.co.ke`
- Gmail message ID: `1a1a1948392bf343`
- No CV attachment was present.
- Action: prepare a separate CV follow-up only after confirming the address is still appropriate.

### Tower SACCO

- Recipient: `info@towersacco.co.ke`
- Gmail message ID: `1a1a1a737e070851`
- No CV attachment was present.
- Action: prepare a separate CV follow-up only after confirming the address is still appropriate.

## Evidence interpretation

- `SENT` means Gmail records the message as sent. It does not prove recipient delivery or reading.
- `No failure notice found` means no bounce was present in the inspected thread at verification time. It is not a delivery receipt.
- The 31 rows in the send log were matched to the tracker, but their Gmail threads and attachment metadata were not re-inspected in this pass. Their attachment status remains based on the original tracker.
- The original contacts CSV and send log were not overwritten. The reconciled CSV adds evidence columns and preserves original fields.
- No messages were sent, replied to, marked read, archived, deleted or otherwise modified during verification.

## Recommended next actions

1. Correct or replace the KCB Kencom SACCO contact using a verified official route.
2. Prepare separate CV follow-ups for Acumen DT SACCO and Tower SACCO. These should not be sent without review.
3. Inspect the 31 send-log message IDs in Gmail to independently verify their attachment metadata and any later delivery failures.
4. Start ongoing read-only Gmail reply monitoring for all 53 outreach records.
