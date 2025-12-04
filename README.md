# HTB "Gavel" — Automated Auction Rule → RCE Exploit


This repository contains an automated Python exploit for the Hack The Box machine **Gavel**.  
It chains several application flaws to obtain a **remote shell** as the auction user:

- Valid credentials for the `auctioneer` user
- Server-side auction “rules” that are executed when bids are processed
- Ability to write arbitrary PHP files into `includes/`
- Triggering a **reverse shell** via a generated PHP payload

> ⚠️ **For CTF / lab use only.**  
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
