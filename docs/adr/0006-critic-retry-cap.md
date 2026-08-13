---
status: accepted
revisit-after: 2027-02-01
---

# Three critic-pass attempts per group, then abandon that group only

A group that fails its critic pass is retried at most three times and then marked
`failed_abandoned`. The cap exists because a fourth attempt has never fixed
anything the third did not, and an uncapped retry burns generation budget on a
composition that is wrong.

**The part that is easy to get wrong:** abandoning a group must **not** delete
the Gelato product or the Etsy listing. Under one-listing-per-artwork those
belong to the *candidate*, and other groups — published or still pending — depend
on them surviving. Abandoning means: mark the group, exclude its sizes and images
from the listing build, leave the shared product alone.

At the primary-group level the same failure still triggers the Go/Hold/Kill
fallback, because the primary group is decided first and no shared product exists
yet if it fails.
