# Lead Email Draft and Approval Workflow

The E-mail központ is a lead-linked drafting workspace. It does not send mail.

## Flow

1. Only leads already approved in the Leadkezelő appear in the generation pool.
2. An admin/operator can generate missing drafts in a deliberate batch action. One current draft is stored per lead.
3. Draft generation uses the saved company research and dossier facts. Unsupported claims, invented contacts and guessed recipient addresses are prohibited.
4. The recipient address is entered with a public source URL and must be saved before the draft can be approved. The address is not inferred from a company domain or model output.
5. The user edits the subject/body and saves a revision. Revisions and workflow events are append-only.
6. A separate approval action moves the draft into the Jóváhagyott e-mailek tab. This is not a send queue and does not grant contact consent.
7. Rejection requires a fixed feedback category and a written explanation. Feedback is append-only and updates a small global style profile:
   - too_formal -> direct formality
   - too_long -> concise
   - too_generic -> high personalization
   - not_persuasive -> direct assertiveness
   - other -> recorded without changing the profile

## Safety

- Only authenticated admin/operator users can generate, edit, approve or reject drafts.
- Reader access is read-only. RLS is enabled on all workflow tables.
- No service-role dashboard write bypass is introduced.
- Recipient address and its source must be supplied by a human; the AI must not invent contact data.
- Lead approval, draft approval, consent, and outbound delivery are separate states.
- The outbound email hard gate in `email_utils.py` remains disabled. No dispatcher or automatic sender is enabled by this feature.
- No model retraining occurs. Free-text rejection notes are audit feedback, not executable prompt instructions.
- Migration `20261127170000_lead_email_drafting_and_feedback.sql` is repository-only until separately reviewed and applied.

## Dashboard

The sidebar has a dedicated E-mail központ page with Piszkozatok, Jóváhagyott e-mailek, Elutasított and Stílusprofil tabs. The approved tab is a review archive only; it does not send or enqueue messages.

## Források és verzióelőzmények a dashboardon

- A piszkozat kártyáján lenyitható cégdosszié mutatja a kutatási jegyzeteket és kizárólag a biztonságos, nyilvános URL-lel rendelkező tényeket.
- A jóváhagyott e-mail listában külön megnyitható a címzett e-mail-címének megadott forrása, valamint a személyre szabáshoz használt dossier-források.
- A piszkozatoknál az utolsó öt mentett verzió megtekinthető; a verziótörténet append-only.
- A forráslinkek csak HTTP(S) URL-ek lehetnek, localhost és privát IP címek nem jeleníthetők meg hivatkozásként.


## Contact authorization, suppression and non-sending queue

- Contact permission is recorded per lead and normalized recipient address. The record requires a reviewed legal-basis category, a written evidence note, the reviewing admin/operator and verification timestamp; an HTTPS evidence URL and expiry may also be supplied.
- Supported basis labels are explicit consent, reviewed legitimate interest, contractual necessity, and other reviewed basis. Selecting a label is an internal record, not legal advice or proof that the underlying processing is lawful.
- Revoking permission automatically adds the address to the global suppression list. A suppressed address blocks all leads using that address; this interface does not provide an unsuppress action.
- An admin/operator can re-evaluate an approved draft. The eligibility RPC checks the draft approval, current permission for the exact lead/address pair, expiry and global suppression.
- Queue states are `blocked`, `ready_for_manual_review` and `cancelled`. The `ready_for_manual_review` state is only an eligibility result; it is not a delivery authorization or an active send job.
- Suppression immediately changes existing non-cancelled queue rows for that address to blocked. Permission events and queue events are append-only.
- No worker, scheduler, provider call or delivery action is connected to this queue. `EMAIL_DELIVERY_ENABLED` in `email_utils.py` remains hard-coded to `False`; actual outbound delivery stays disabled pending a separate review and explicit authorization.
- The migration is repository-only and must not be applied to production as part of this PR.

## Implementation inventory and release boundary (2026-11-27)

The current PR #35 implementation is split across these repository components:

- `supabase/migrations/20261127170000_lead_email_drafting_and_feedback.sql`: lead-linked drafts, append-only revisions/events, separate approval/rejection and structured global style feedback.
- `supabase/migrations/20261127180000_lead_email_contact_permissions_and_queue.sql`: per-lead/recipient permission evidence, permission audit events, global suppression and a non-sending eligibility register.
- `lead_email_dashboard.py`: draft generation/review, recipient source capture, permission review, suppression controls and eligibility re-evaluation.
- `email_utils.py`: outbound delivery hard gate. `EMAIL_DELIVERY_ENABLED = False` is a code-level constant; environment configuration cannot turn delivery on.
- `tests/test_lead_email_dashboard.py`: helper validation and a regression assertion that the outbound delivery gate raises while disabled.

### State separation

The workflow deliberately keeps these independent: lead approval, draft approval, contact permission, suppression status and delivery capability. A lead being accepted does not authorize contact. An approved draft does not bypass permission checks. A queue row marked `ready_for_manual_review` means only that the current eligibility checks passed; it is not a scheduled job, send authorization or provider request. Suppression blocks matching recipients globally, and permission revocation also creates a suppression entry.

### Not implemented / not authorized

There is no sender worker, scheduler, provider dispatch, automatic retry loop or dashboard send button connected to this workflow. No outbound email has been sent by this implementation. Do not remove the hard gate, apply these migrations to production, or enable delivery without a separate security/compliance review and explicit authorization.

### Latest CI observation

For PR #35 HEAD `bd8be5a87ce92b3934626e13351a50279e78fd34`, automatic workflow run [46010157939](https://github.com/tamaszsolt2005-hub/jarvis-core/actions/runs/46010157939) was observed in progress. At that observation, the PostgreSQL research integration and backup/restore jobs had succeeded; the main test job was still installing Playwright browsers and had not yet reached compile/test steps. This is a point-in-time observation, not a final CI result. No local tests or manual workflow dispatch were run.


## Bejövő ügyfélválaszok – emberi döntés kötelező

- Az ütemezett `.github/workflows/email-automation.yml` csak akkor futtat inbox-ellenőrzést, ha az `EMAIL_INBOX_MONITOR_ENABLED=true` és a szükséges IMAP/Supabase titkok rendelkezésre állnak.
- Az `email_inbox.py` a bejövő üzenetet a feladó e-mail-címe alapján leadhez kapcsolja, osztályozza (`interested`, `later`, `rejected`, `opt_out`, `unknown`), és leállítja a további utánkövetést.
- A feldolgozott válaszról naplóbejegyzés készül. Az E-mail központ **Beérkezett válaszok** füle megjeleníti az új eseményeket; az érdeklődő válasz külön kiemelést kap.
- **Automatikus válaszadás tilos:** JARVIS nem ír vissza, nem küld ajánlatot, nem indít új megkeresést és nem folytatja az utánkövetést. A következő lépésről kizárólag a felhasználó dönthet.
- Ez az értesítés jelenleg az alkalmazáson belül érhető el, amikor megnyitod az E-mail központot. E-mailes, mobil push vagy más külső értesítési csatorna nincs bekapcsolva.
- A levél előnézete rövidített naplóbejegyzés; a teljes levelezési szál és válaszküldő felület nem része ennek a változtatásnak.
