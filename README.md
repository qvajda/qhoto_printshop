Qhoto - Print Shop Assistant: Qhoto - Print Shop Assistant is a personal tool I use to manage product listings, inventory, and shop sections for my own single Etsy shop. It creates and updates my own listings only and does not interact with or manage any other seller's shop. All purchases and checkout are completed entirely through Etsy's own platform — this application does not process payments or bypass Etsy checkout in any way.

## Setup

One-time, per checkout: `git config core.hooksPath scripts/git-hooks` — wires up the `post-merge` hook that runs `migrate.py --post-merge` after every pull, so a merged migration reaches this checkout's DB without a human remembering to type the command.
