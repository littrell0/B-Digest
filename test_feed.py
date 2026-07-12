"""测试 B站 web feed API"""
import asyncio, json, httpx, os

async def test():
    # 从 settings.json 读取 cookie
    settings_file = os.path.join(os.path.dirname(__file__), "settings.json")
    with open(settings_file, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    sessdata = cfg.get("bili_sessdata", "")
    if not sessdata:
        print("No SESSDATA found in settings.json")
        return

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cookie": f"SESSDATA={sessdata}",
    }

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            "https://api.bilibili.com/x/web-feed/feed",
            headers=headers,
            params={"pn": 1, "ps": 5},
        )
        print("Status:", r.status_code)
        print("Content-Type:", r.headers.get("content-type"))
        print("Body[:500]:", r.text[:500])
        if r.status_code == 412:
            print("GOT 412 - need more cookies/headers")
            return
        d = r.json()
        print("Code:", d.get("code"))
        print("Message:", d.get("message"))
        if d["code"] == 0:
            items = d["data"]["list"]
            print(f"Items: {len(items)}")
            for item in items[:5]:
                t = item.get("type", "?")
                title = item.get("title", "?")[:50]
                author = item.get("owner", {}).get("name", "?")
                print(f"  [{t}] {author}: {title}")

if __name__ == "__main__":
    asyncio.run(test())
