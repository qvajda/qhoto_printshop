---
status: accepted
revisit-after: 2027-02-01
---

# One Etsy listing per artwork, with sizes as variants

A candidate's six print sizes are variants of **one** Etsy listing, not one
listing per aspect-ratio group. The alternative — a listing per group — was what
v4.11 shipped, and it split one design across up to three storefront entries
competing with each other.

**Why it is hard to reverse:** adding a variant to an existing Gelato product has
no API path. `PUT` on the product resource returns `200` and silently drops the
addition while severing the Etsy sync; the `/variants` sub-resource is a
different, incompatible custom-priced flow; re-`create-from-template` with the
same title creates a second product. Confirmed live (GL-22a Q2). The listing is
therefore created **once**, when all three groups have reached a terminal
decision — never incrementally.

**Consequence that surprises readers of the schema:** `group_products` is a
misnomer. It is the *candidate's* listing record, and `gelato_product_id` is one
nullable column on it, NULL for the whole multi-day review window. Anything
sweeping `pending` rows with no product id must know that is the normal state,
not a stranded one.
