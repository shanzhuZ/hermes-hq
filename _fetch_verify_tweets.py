import asyncio, json, os, sys
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, "D:/environment/python/Lib/site-packages")

from twitter_mcp._vendor.twikit import Client  # noqa

COOKIES = Path("C:/Users/zhr/.config/twitter-mcp/cookies.json")
PROXY = os.environ.get("TWITTER_PROXY") or os.environ.get("HTTPS_PROXY") or None

async def main():
    cookies = json.loads(COOKIES.read_text(encoding="utf-8"))
    c = Client("en", proxy=PROXY)
    c.set_cookies({"auth_token": cookies["auth_token"], "ct0": cookies["ct0"]})
    user = await c.get_user_by_screen_name("whyyoutouzhele")
    out = []
    cursor = None
    for _ in range(7):
        res = await c.get_user_tweets(user.id, "Tweets", count=40, cursor=cursor)
        for t in res:
            out.append({
                "id": str(t.id),
                "created_at": str(t.created_at),
                "text": t.text,
                "likes": getattr(t, "favorite_count", None),
                "rts": getattr(t, "retweet_count", None),
                "replies": getattr(t, "reply_count", None),
                "views": getattr(t, "view_count", None),
                "media": [m.type for m in (t.media or [])] if getattr(t, "media", None) else [],
            })
        cursor = getattr(res, "next_cursor", None)
        if not cursor:
            break
        if len(out) >= 240:
            break
    # dedupe
    seen = set(); uniq = []
    for t in out:
        if t["id"] in seen: continue
        seen.add(t["id"]); uniq.append(t)
    Path("D:/hermes-hq/_verify_whyyoutouzhele.json").write_text(
        json.dumps(uniq, ensure_ascii=False, indent=1), encoding="utf-8")
    print("count", len(uniq))
    print("range", uniq[-1]["created_at"], "->", uniq[0]["created_at"])

asyncio.run(main())
