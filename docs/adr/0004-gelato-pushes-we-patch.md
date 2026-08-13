---
status: accepted
revisit-after: 2027-02-01
---

# Gelato creates the Etsy listing; we patch it afterwards

The Gelato store is Etsy-connected and auto-creates the listing on product
creation. The pipeline does **not** create Etsy listings itself: after Gelato's
async sync we resolve the Etsy `listing_id` from the Gelato product's
`externalId` and PATCH it (`updateListing` + `updateListingInventory`).

The alternative — creating the listing ourselves — was tried in the first live
run and collided with Gelato's push, producing duplicate and half-synced
listings. `create_draft_listing` is never called.

**Consequence:** every field that used to be set at create time (title,
description, tags, section, partner, `who_made`, per-variant price) moves to the
patch. A field that is only settable at creation is, for this pipeline, not
settable at all.
