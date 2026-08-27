# Safety Decision Table

| Data or action | Default handling | Requires explicit approval |
| --- | --- | --- |
| Aggregate debt totals | Can show in chat | No |
| Apartment or premise number with debt | Show only for authorized debtor work | For publication or external channels |
| Owner/resident names | Do not show or store | Only if strictly needed and user explicitly asks |
| Phone numbers, emails | Do not commit or include in final answers | Only transiently for an authorized contact task |
| `userId`, `tenantId`, bearer token, refresh token | Do not print, store in committed files, or expose | Never expose in final answers |
| DAH raw responses | Summarize or sanitize | Before saving or sharing |
| Messenger or tenant notification send | Preview first | Always |
| DAH publication save | Preview body first | Always |
| Feedback order status update | Preview when ambiguous | Required unless the target is unambiguous |
| Bank transactions | Summarize relevant matches | Before posting externally |

Use aggregate reporting by default. Use individual apartment/premise details only
when the user is performing an authorized operational task.

Write artifacts must not contain credentials, local machine paths, phone numbers,
emails, personal names, raw `userId`, or raw `tenantId`.
