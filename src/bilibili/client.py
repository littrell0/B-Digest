"""
B站 客户端 — bilibili-api-python (WBI签名) + 注入浏览器 Session
"""
import asyncio
import httpx
import logging
import random
import time
from datetime import datetime, timedelta

logger = logging.getLogger("bili_summarizer")


def _rand(a, b):
    """随机浮点延迟（秒），均匀分布"""
    return random.uniform(a, b)


def _rand_norm(lo, hi):
    """正态分布随机延迟，mu=(lo+hi)/2，sigma=(hi-lo)/6，截断到[lo, hi]"""
    mu = (lo + hi) / 2
    sigma = (hi - lo) / 6  # 99.7% 落在 [lo, hi]
    val = random.gauss(mu, sigma)
    return max(lo, min(hi, val))


def _fix_headers():
    """修改 bilibili-api 默认请求头，伪装成 Windows Chrome"""
    import bilibili_api
    bilibili_api.HEADERS.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })


class BilibiliClient:
    def __init__(self, sessdata: str = "", bili_jct: str = "", buvid3: str = ""):
        self.sessdata = sessdata
        self.bili_jct = bili_jct
        self.buvid3 = buvid3
        self._username = None
        self._uid = None
        _fix_headers()

    @property
    def credential(self):
        from bilibili_api import Credential
        return Credential(sessdata=self.sessdata, bili_jct=self.bili_jct, buvid3=self.buvid3)

    def test_login(self) -> dict:
        try:
            return asyncio.run(self._test_login_async())
        except Exception as e:
            return {"ok": False, "error": str(e)[:100]}

    async def _test_login_async(self) -> dict:
        from bilibili_api.user import get_self_info
        info = await get_self_info(self.credential)
        self._username = info.get("name", "")
        self._uid = str(info.get("mid", ""))
        return {"ok": True, "name": self._username, "uid": self._uid}

    def get_username(self) -> str:
        return self._username or ""

    def get_followings(self, max_pages: int = 8, page_size: int = 50) -> list:
        """获取关注UP主列表（同步）"""
        return asyncio.run(self._get_followings_async(max_pages, page_size))

    async def _get_followings_async(self, max_pages: int, page_size: int) -> list:
        """获取关注列表"""
        from bilibili_api.user import User
        me = User(uid=int(self._uid), credential=self.credential)
        followings = []
        for pn in range(1, max_pages + 1):
            try:
                data = await me.get_followings(pn=pn, ps=page_size)
                items = data.get("list", [])
                if not items:
                    break
                for item in items:
                    followings.append({
                        "uid": str(item.get("mid", "")),
                        "name": item.get("uname", ""),
                    })
                await asyncio.sleep(_rand(2, 3))
            except Exception as e:
                msg = str(e)[:60]
                logger.warning("关注p%d: %s", pn, msg)
                if "412" in msg:
                    break
        return followings

    def get_recent_videos_from_followings(
        self, hours: int = 24, excluded_uids: list = None, progress_callback=None,
    ) -> list:
        return asyncio.run(self._get_recent_async(hours, excluded_uids or [], progress_callback))

    async def _get_recent_async(self, hours: int, excluded_uids: list, progress_callback) -> list:
        from bilibili_api.user import User

        # 关注列表
        if progress_callback:
            progress_callback(0, 0, "获取关注列表...")

        followings = await self._get_followings_async(max_pages=6, page_size=50)

        # 过滤排除的UP主
        if excluded_uids:
            excluded_set = set(excluded_uids)
            followings = [u for u in followings if u["uid"] not in excluded_set]
            logger.info("已排除 %d 个UP主", len(excluded_uids) - len([u for u in followings if u["uid"] in excluded_set]))

        total = len(followings)
        if total == 0:
            return []

        if progress_callback:
            progress_callback(0, total, f"共 {total} 个UP主 · 逐个检查中 (间隔较长，请耐心等待)")

        cutoff = datetime.now() - timedelta(hours=hours)
        recent_videos = []
        failed_up = []  # (up, fail_count)

        # 辅助函数：尝试获取UP主视频
        async def _fetch_up(up: dict) -> list:
            up_user = User(uid=int(up["uid"]), credential=self.credential)
            data = await up_user.get_videos(pn=1, ps=30)
            vlist = data.get("list", {}).get("vlist", [])
            return vlist

        # 第一轮：遍历所有UP主
        for i, up in enumerate(followings):
            if i > 0:
                await asyncio.sleep(_rand_norm(6, 12))
            else:
                await asyncio.sleep(_rand(2, 3))

            if progress_callback:
                progress_callback(i + 1, total, f"{up['name']} ({i+1}/{total})")

            try:
                vlist = await _fetch_up(up)
            except Exception as e:
                msg = str(e)
                if "412" in msg:
                    logger.info("412 风控: %s（暂缓，稍后重试）", up["name"])
                    failed_up.append({"up": up, "fails": 1})
                    if progress_callback:
                        progress_callback(i + 1, total,
                            f"系统限流，暂缓后继续 ({i+1}/{total})")
                    await asyncio.sleep(_rand(15, 25))
                else:
                    logger.error("%s: %s", up["name"], str(e)[:100])
                continue

            for v in vlist:
                pubtime = datetime.fromtimestamp(v.get("created", 0))
                if pubtime >= cutoff:
                    recent_videos.append({
                        "bvid": v.get("bvid", ""),
                        "title": v.get("title", ""),
                        "pubdate": v.get("created", 0),
                        "duration": v.get("length", ""),
                        "author": up["name"],
                        "author_uid": up["uid"],
                        "pubdate_str": pubtime.strftime("%m-%d %H:%M"),
                    })

        # 重试轮：最多4次
        retry_round = 1
        while failed_up and retry_round < 4:
            await asyncio.sleep(_rand(15, 20))
            total_failed = len(failed_up)
            logger.info("重试第%d轮: %d个", retry_round, total_failed)

            still_failed = []
            for j, item in enumerate(failed_up):
                up = item["up"]
                if progress_callback:
                    progress_callback(j + 1, total_failed,
                        f"重试第{retry_round}轮 · {up['name']} ({j+1}/{total_failed})")

                try:
                    vlist = await _fetch_up(up)
                    for v in vlist:
                        pubtime = datetime.fromtimestamp(v.get("created", 0))
                        if pubtime >= cutoff:
                            recent_videos.append({
                                "bvid": v.get("bvid", ""),
                                "title": v.get("title", ""),
                                "pubdate": v.get("created", 0),
                                "duration": v.get("length", ""),
                                "author": up["name"],
                                "author_uid": up["uid"],
                                "pubdate_str": pubtime.strftime("%m-%d %H:%M"),
                            })
                    logger.info("重试成功: %s", up["name"])
                    await asyncio.sleep(_rand(10, 13))
                except Exception as e:
                    if "412" in str(e):
                        fail_count = item["fails"] + 1
                        logger.info("重试仍412: %s (第%d次)", up["name"], fail_count)
                        still_failed.append({"up": up, "fails": fail_count})
                        # 渐进退避
                        if fail_count == 1:
                            delay = _rand(10, 13)
                        elif fail_count == 2:
                            delay = _rand(18, 22)
                        else:
                            delay = _rand(60, 65)
                        await asyncio.sleep(delay)
                    else:
                        logger.error("%s: %s", up["name"], str(e)[:100])

            failed_up = still_failed
            retry_round += 1

        # 最终仍然失败的，在GUI报告
        for item in failed_up:
            name = item["up"]["name"]
            logger.error("%s 信息读取失败（重试%d次）", name, item["fails"])
            if progress_callback:
                progress_callback(0, 0, f"{name} 信息读取失败")

        recent_videos.sort(key=lambda x: x["pubdate"], reverse=True)
        logger.info("完成: %d视频, %d个UP主失败", len(recent_videos), len(failed_up))
        return recent_videos


# ===== 搜索（无需登录） =====

_last_search_time = 0.0

def search_videos(keyword: str, page: int = 1, duration: int = 0) -> dict:
    """
    B站视频搜索（无需Cookie）

    Args:
        keyword: 搜索关键词
        page: 页码
        duration: 时长筛选 0=全部 1=<10min 2=10-30min 3=30-60min 4=>60min

    Returns: {"numResults": int, "result": [...]}
    """
    # 搜索冷却：至少间隔 5 秒
    global _last_search_time
    elapsed = time.time() - _last_search_time
    if elapsed < 5:
        time.sleep(5 - elapsed)
    _last_search_time = time.time()

    resp = httpx.get(
        "https://api.bilibili.com/x/web-interface/search/type",
        params={
            "search_type": "video", "keyword": keyword,
            "page": page, "duration": duration, "order": "default",
        },
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "Referer": "https://www.bilibili.com/",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "application/json, text/plain, */*",
        },
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(data.get("message", "搜索失败"))
    return data["data"]
