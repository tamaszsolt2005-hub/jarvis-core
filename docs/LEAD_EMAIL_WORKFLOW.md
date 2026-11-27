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
