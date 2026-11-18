#!/usr/bin/env python3
"""Print Walk Chicago's feedback notes, newest first, straight from the KV namespace.

Uses the Cloudflare API with CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID from the environment,
so no FEEDBACK_KEY is needed. (The /api/feedback GET route still works for anyone who has that key.)

    python3 scripts/read_feedback.py            # readable list
    python3 scripts/read_feedback.py --json     # raw JSON
"""
import json, os, sys, urllib.parse, urllib.request

NAMESPACE = "b27b2c91d739401da8d7f750f06c5aa2"  # walk-chicago-feedback (wrangler.toml)
token, account = os.environ.get("CLOUDFLARE_API_TOKEN"), os.environ.get("CLOUDFLARE_ACCOUNT_ID")
if not token or not account:
    sys.exit("Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID")
base = f"https://api.cloudflare.com/client/v4/accounts/{account}/storage/kv/namespaces/{NAMESPACE}"

def get(path, raw=False):
    req = urllib.request.Request(base + path, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return body if raw else json.loads(body)

keys, cursor = [], ""
while True:
    page = get("/keys?prefix=note:&limit=1000" + (f"&cursor={urllib.parse.quote(cursor)}" if cursor else ""))
    keys += [k["name"] for k in page["result"]]
    cursor = page.get("result_info", {}).get("cursor") or ""
    if not cursor:
        break
notes = [json.loads(get("/values/" + urllib.parse.quote(k, safe=""), raw=True)) for k in keys]  # keys sort newest first
if "--json" in sys.argv:
    print(json.dumps({"notes": notes}, indent=1, ensure_ascii=False))
else:
    for n in notes:
        where = f"{n.get('tour')} stop {n['stop'] + 1 if isinstance(n.get('stop'), int) else '-'}"
        if n.get("deeper"):
            where += f" deeper {n['deeper']} ({n.get('chapterTitle')})"
        print(f"{n.get('at', '')[:16]}  {where}  {n.get('stopTitle') or ''}  [{n.get('app')}]")
        print(f"   {n.get('note')}")
        if n.get("sentence"):
            print(f"   playing: {n['sentence'][:160]}")
    print(f"{len(notes)} notes")
