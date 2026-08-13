# GL-11 — email draft: request to exit Etsy Developer Mode (2026-08-06)

**Status: draft for the owner to send. Nothing is sent from here.** Per
CLAUDE.md §4, a communication in your name needs your explicit go-ahead —
this document is the plan, you are the send button.

**To:** developer@etsy.com
**From:** the email on the Etsy account that owns the shop (use the account
email, not an alias — a mismatch is the most common reason these bounce
between support queues)
**Subject:** Request to disable Developer Mode — shop [SHOP NAME] (shop ID
[SHOP ID])

---

## Before you send — fill these four in

1. **[SHOP NAME]** and **[SHOP ID]** — your shop's public name and numeric id
   (`ETSY_SHOP_ID` in `.env`).
2. **[APP NAME]** — the name of your registered Etsy app, as it appears in
   your developer account.
3. **[KEYSTRING]** — your app's keystring (`ETSY_API_KEY`). Safe to include:
   it is the public half, it is what Etsy indexes these requests by, and
   omitting it is what turns one email into three. **Do not include
   `ETSY_API_SECRET`, the access token, or the refresh token.**
4. **The date** you switched Developer Mode on, if you have it. Approximate is
   fine; "around mid-July 2026" is better than nothing.

---

## Draft

> Hello,
>
> I'd like to request that Developer Mode be disabled for my shop.
>
> Shop: **[SHOP NAME]** (shop ID **[SHOP ID]**)
> App: **[APP NAME]**, keystring **[KEYSTRING]**
> Account email: **[the email you are sending from]**
>
> I switched the shop into Developer Mode in [MONTH 2026] so that I could
> test an Etsy API v3 integration against my own shop without the test
> listings becoming publicly visible or purchasable. That testing is now
> complete: the integration creates listings correctly, patches them with the
> right variations, pricing, images and production partner, and I've verified
> the results against the API and in Shop Manager.
>
> The test listings created during that phase have been deleted. I'm now
> ready to open the shop properly and start publishing real listings, so I
> would like the shop returned to normal (non–Developer Mode) status.
>
> Please let me know if you need anything further from me to process this, or
> if there are steps I should take on my side first.
>
> Thank you,
> Quentin Vajda

---

## Notes on the draft, in case you want to change it

- **It asks one question and answers the two Etsy will ask back** — which
  shop, and is the testing actually finished. Support threads that need a
  round trip to establish basic identifiers lose days, and days are the whole
  reason this email is on the critical path.
- **It does not mention the pipeline, AI generation, print-on-demand, Gelato,
  or how listings are produced.** Not concealment — none of it is relevant to
  the request, and every extra detail is a surface for a support agent to
  route the ticket somewhere else or ask a follow-up. Your AI disclosure
  obligation lives on the listings themselves (`who_made: i_did` plus the
  description text, and whatever GL-37 concludes about the Creativity
  Standards fields), not in this email.
- **"The test listings have been deleted" must be true when you send it.**
  Right now candidate 42's draft (`4549960823`) is still live, and 40/41's
  are already gone. Either delete 42 first, or soften the line to "are being
  cleaned up". **Do not delete 42 before the soak's live night** — GL-36's
  reconcile needs it alive as its negative control. If that ordering is
  awkward, send the email with the softer wording; the email is worth more
  today than the sentence is.
- **Tone is deliberately flat and administrative.** This is a queue, not a
  conversation.

## After you send

- Expect a lead time you do not control; that is the entire point of sending
  it now rather than after the soak.
- Log the send date in `CHANGELOG.md` — GL-11's clock starts at the send, and
  the plan currently has no record of when that was.
- If there's no reply in ~10 business days, reply in the same thread rather
  than opening a new one.
- Reverting Developer Mode changes what a shopper sees, not what the API
  does, so **nothing in the pipeline needs to change when it lands** — but
  GL-29's activation becomes visible to the public, which is why GL-29 stays
  behind its flag until you want that.
