# HTB "Gavel" — Automated Auction Rule → RCE Exploit


This repository contains an automated Python exploit for the Hack The Box machine **Gavel**.  
It chains several application flaws to obtain a **remote shell** as the auction user:

- Valid credentials for the `auctioneer` user
- Server-side auction “rules” that are executed when bids are processed
- Ability to write arbitrary PHP files into `includes/`
- Triggering a **reverse shell** via a generated PHP payload

> **For CTF / lab use only.**  
> This PoC is tailored for the HTB environment (`gavel.htb`) and must **not** be used against systems you don’t own or have explicit permission to test.

---

## Features

-  Logs in as `auctioneer` (credentials can be customized in the script)
-  Enumerates active auctions from `bidding.php`
-  Automatically picks candidate auctions based on `data-end` timestamps
-  Injects a PHP reverse shell using the admin “rule” mechanic
-  Places a bid via `bid_handler.php` to trigger the injected rule
-  Starts a `nc` listener and launches the webshell automatically
-  Randomized shell name like `shell_ab12cd34.php` for each run

---

## How it works (high-level)

1. **Login**  
   The script performs a basic login against:

   - `http://gavel.htb/login.php`

   using the hardcoded credentials:

   ```python
   username = "auctioneer"
   password = "midnight1"
   ```
You can change these at the top of the script if needed.

2. **Auction discovery**
It fetches:

http://gavel.htb/bidding.php

then parses each auction card:

Extracts auction_id

3. **Extracts data-end**

Extracts current bid (Current: value)

It prefers auctions whose data-end is still in the future; if all appear ended, it falls back to all of them.

Rule injection → file write
For each candidate auction, it sends a POST to:

http://gavel.htb/admin.php

with a crafted rule like:

```
file_put_contents('shell_xxx.php', '<?php ... reverse shell ... ?>'); return true;
```

This writes a PHP file into the includes/ directory with a randomized name such as shell_ab12cd34.php.

4. **Triggers a bid**
It then sends a multipart/form-data POST to:

http://gavel.htb/includes/bid_handler.php

with:

auction_id

bid_amount = current bid + 1

A successful bid triggers the injected rule for that auction, causing the PHP reverse shell to be written.

5. **Reverse shell execution**
Finally, it:

Starts a local nc -lvnp <port> listener

Performs a GET request to:
http://gavel.htb/includes/<generated_shell_name>

The PHP payload connects back to the listener with an interactive /bin/bash -i session.
