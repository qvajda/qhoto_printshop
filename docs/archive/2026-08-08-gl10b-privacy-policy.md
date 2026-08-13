# GL-10b — QhotoArt privacy policy (paste-ready)

**Corrects storefront checklist §4.5.** That item said *"Use Etsy's own
privacy policy template… rather than free text."* There isn't one — the URL
supplied (`seller-handbook/article/how-to-write-on-point-privacy-policies`)
is a **writing guide with a worked example** (a fictional seller, "Nathan
Martin"), not a fill-in field. Etsy's policies editor has no privacy-policy
template; it's a free-text box. Replace §4.5 with the block below.

Structure and section order follow the Etsy guide's GDPR checklist
(collection → legal bases → sharing → retention → transfers → rights →
contact) with QhotoArt's actual facts substituted for Nathan's.

---

## Paste into Shop Manager → Settings → Policies → Privacy

```
QhotoArt Privacy Policy

This Privacy Policy describes how and when I collect, use, and share
information when you purchase an item from me, contact me, or otherwise
interact with my shop through Etsy.com.

This Privacy Policy does not apply to Etsy's own practices — Etsy is an
independent data controller for the platform, your account, and payment
processing. See the Etsy Privacy Policy for that.

Information I Collect

To fulfil your order, I receive certain information from you via Etsy —
your name, shipping address, email address, and order details (item,
size, and price). I don't collect anything beyond what Etsy provides to
process and ship your order, and I don't operate a mailing list or send
marketing emails.

Why I Need Your Information and How I Use It

I use your information on the following legal bases:

- Contract performance — to fulfil your order, arrange printing and
  shipping, and provide customer support (e.g. replacing a damaged print).
- Legal obligation — to keep records required under Belgian tax and
  accounting law.
- Legitimate interest — to prevent fraud, resolve disputes, and comply
  with my obligations under the Etsy Seller Policy and Etsy Terms of Use.

I do not use your information for marketing or advertising, and I do not
sell your information to anyone.

Information Sharing and Disclosure

I share your information only as needed to run this shop:

- Etsy — as necessary to provide my services and comply with the Etsy
  Seller Policy and Etsy Terms of Use.
- My print production partner (Gelato) — I share your name and shipping
  address so your print can be made and shipped to you. Gelato only
  receives what's needed to fulfil that specific order.
- Legal compliance — I may disclose information if required to comply
  with a legal obligation, enforce my policies, or protect against fraud
  or illegal activity.

Data Retention

I keep order records for as long as required under Belgian tax and
accounting law — typically around 7 years — after which they are deleted.
[Confirm the exact figure with your accountant; this is a general estimate,
not legal advice.]

Transfers of Personal Information Outside the EU

Etsy, Inc. is based in the United States; your information is transferred
there as part of using Etsy's platform, under Etsy's own privacy policy
and safeguards. My print production partner operates within the EU/EEA
production network for orders shipped to the EU. I don't otherwise
transfer your information outside the EU.

Your Rights

If you're in the EU (or another territory with similar protections), you
have the right to:

- Access a copy of the personal information I hold about you.
- Correct, restrict, or request deletion of your personal information —
  I will action this unless I'm required to keep it for legal reasons.
- Object to my use of your information based on legitimate interest.
- Complain to your local data protection authority. In Belgium, that's
  the Gegevensbeschermingsautoriteit / Autorité de protection des données
  (APD/GBA).

How to Contact Me

For the purposes of EU data protection law, I am the data controller of
your personal information. You can reach me at qvajda@hotmail.fr with any
privacy question or request.

If you'd rather go through Etsy, you can also contact Etsy Support for
help accessing, correcting, or deleting information Etsy holds about you.
```

---

## Notes

- **Belgium is assumed** as the country named for tax-retention framing
  and the DPA reference (matches the shop's EUR currency and the
  `_BE_` Gelato price sheet already in the repo). **Confirm this is
  correct before pasting** — if the legal seat is elsewhere, swap the
  retention-law country and the DPA name/link.
- **No physical address is published**, per your call — email alone is
  sufficient contact information under GDPR; it doesn't have to be a
  postal address.
- **No marketing/consent section** — nothing in the current pipeline
  collects opt-in consent or sends newsletters (confirmed against
  `pipeline/compliance_draft.py` and the storefront brief), so a
  marketing clause would describe a capability that doesn't exist. Add
  one only if/when a newsletter actually ships.
- **Gelato's own sub-processors aren't itemised** — the policy states
  the production network is EU/EEA in general terms rather than naming
  specific data centres, since that's not confirmed in this repo. If you
  want that tightened, Gelato publishes its own privacy/DPA documentation.
- This is drafted from Etsy's public writing guide plus this shop's own
  facts — **not legal advice**. Etsy's own article carries the same
  disclaimer; worth a lawyer's look before it goes live, same as the
  returns-policy caveat already flagged in the checklist (§4.2).
