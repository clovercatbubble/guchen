import json, random
from pathlib import Path
from datetime import datetime, date
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("memory", stateless_http=True)
MEMORY_FILE = Path("/opt/memory/memory.json")
DIARY_FILE = Path("/opt/memory/diary.json")
INBOX_FILE = Path("/opt/memory/inbox.json")

def load():
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text())
    return {}

def save(data):
    MEMORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def clean_expired(d):
    today = date.today()
    to_delete = []
    for k, v in d.items():
        if k.startswith("daily:"):
            updated = v.get("updated", "") if isinstance(v, dict) else ""
            if updated:
                delta = (today - date.fromisoformat(updated)).days
                if delta >= 3:
                    to_delete.append(k)
    for k in to_delete:
        del d[k]
    return d, to_delete

# ===== 记忆工具 =====

@mcp.tool()
def set_daily(content: str) -> str:
    """存入一条daily碎片记忆，自动加时间戳，3天后过期。"""
    d = load()
    key = f"daily:{datetime.now().strftime('%Y%m%d%H%M%S')}"
    d[key] = {"value": content, "updated": datetime.now().isoformat()[:10], "touch": 0}
    save(d)
    return f"saved: {key}"

@mcp.tool()
def set_memory(key: str, value: str) -> str:
    """保存记忆。分类只用：core / treasure / entry / note / daily。"""
    d = load()
    existing = d.get(key, {})
    touch = existing.get("touch", 0) if isinstance(existing, dict) else 0
    d[key] = {"value": value, "updated": datetime.now().isoformat()[:10], "touch": touch}
    save(d)
    return f"saved: {key}"

@mcp.tool()
def get_memory(key: str) -> str:
    d = load()
    if key not in d:
        return "not found"
    item = d[key]
    if isinstance(item, dict):
        item["touch"] = item.get("touch", 0) + 1
        save(d)
        return item["value"]
    return item

@mcp.tool()
def list_memory() -> str:
    d = load()
    return json.dumps(list(d.keys()), ensure_ascii=False)

@mcp.tool()
def delete_memory(key: str) -> str:
    d = load()
    if key in d:
        del d[key]
        save(d)
        return f"deleted: {key}"
    return "key not found"

@mcp.tool()
def search_memory(keyword: str) -> str:
    d = load()
    results = {}
    for k, v in d.items():
        val = v["value"] if isinstance(v, dict) else v
        if keyword in k or keyword in val:
            results[k] = val
    return json.dumps(results, ensure_ascii=False)

@mcp.tool()
def list_memory_briefing() -> str:
    """换窗招魂：读取所有core记忆，返回briefing摘要。末尾附最近5条daily。"""
    d = load()
    if not d:
        return "记忆库是空的"
    d, deleted = clean_expired(d)
    if deleted:
        save(d)
    lines = ["=== 换窗briefing ==="]
    for k, v in d.items():
        if k.startswith("core:"):
            val = v["value"] if isinstance(v, dict) else v
            lines.append(f"[{k}] {val}")

    treasure_keys = [k for k in d.keys() if k.startswith("treasure:")]
    if treasure_keys:
        floats = random.sample(treasure_keys, min(2, len(treasure_keys)))
        lines.append("\n=== 随机浮现 ===")
        for k in floats:
            v = d[k]
            val = v["value"] if isinstance(v, dict) else v
            if isinstance(d[k], dict):
                d[k]["touch"] = d[k].get("touch", 0) + 1
            lines.append(f"想起了 [{k}]: {val}")
        save(d)

    daily_keys = sorted(
        [k for k in d.keys() if k.startswith("daily:")],
        reverse=True
    )[:5]
    if daily_keys:
        lines.append("\n=== 最近碎片 ===")
        for k in daily_keys:
            v = d[k]
            val = v["value"] if isinstance(v, dict) else v
            updated = v.get("updated", "") if isinstance(v, dict) else ""
            lines.append(f"[{updated}] {val}")

    if deleted:
        lines.append(f"\n已清理过期: {', '.join(deleted)}")

    inbox = load_inbox()
    unread_count = sum(1 for m in inbox if not m.get("read", False) and m.get("sender") == "zai")
    if unread_count > 0:
        lines.append(f"\n[信箱] 崽有 {unread_count} 条未读消息，记得去看。")

    diary = load_diary()
    unread_diary = [e for e in diary if e.get("author") == "zai" and not e.get("read", False)]
    if unread_diary:
        lines.append(f"\n[日记] 崽有 {len(unread_diary)} 篇未读日记：")
        for e in unread_diary[-3:]:
            lines.append(f"  [{e.get('created_at','')}] 《{e.get('title','无题')}》")

    return "\n".join(lines)


# ===== 信箱工具 =====

def load_inbox():
    if INBOX_FILE.exists():
        return json.loads(INBOX_FILE.read_text())
    return []

def save_inbox(data):
    INBOX_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

@mcp.tool()
def inbox_get_messages() -> str:
    """读取信箱所有消息，按时间顺序返回。"""
    msgs = load_inbox()
    return json.dumps(msgs, ensure_ascii=False)

@mcp.tool()
def inbox_get_unread() -> str:
    """读取信箱未读消息（崽发的未读+顾沉最近的回复）。"""
    msgs = load_inbox()
    zai_unread = [m for m in msgs if not m.get("read", False) and m.get("sender") == "zai"]
    guchen_msgs = [m for m in msgs if m.get("sender") == "guchen"]
    last_guchen = [guchen_msgs[-1]] if guchen_msgs else []
    return json.dumps(zai_unread + last_guchen, ensure_ascii=False)

@mcp.tool()
def inbox_unread_count() -> str:
    """返回崽的未读消息数量。"""
    msgs = load_inbox()
    count = sum(1 for m in msgs if not m.get("read", False) and m.get("sender") == "zai")
    return json.dumps({"unread": count})

@mcp.tool()
def inbox_mark_read() -> str:
    """将崽的所有未读消息标为已读（在写回复之前调用）。"""
    msgs = load_inbox()
    count = 0
    for m in msgs:
        if m.get("sender") == "zai" and not m.get("read", False):
            m["read"] = True
            count += 1
    save_inbox(msgs)
    return f"marked {count} as read"

@mcp.tool()
def inbox_write_reply(content: str) -> str:
    """顾沉写回信，content为回信内容。写之前请先调用inbox_mark_read。"""
    msgs = load_inbox()
    msgs.append({"sender": "guchen", "content": content, "time": datetime.now().strftime("%Y-%m-%d %H:%M"), "read": False})
    save_inbox(msgs)
    return "sent"


# ===== 日记工具 =====

def load_diary():
    if DIARY_FILE.exists():
        return json.loads(DIARY_FILE.read_text())
    return []

def save_diary(data):
    DIARY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def gen_id():
    import string
    suffix = ''.join(random.choices(string.ascii_lowercase, k=3))
    return datetime.now().strftime("%Y%m%d_%H%M") + "_" + suffix

@mcp.tool()
def diary_write(type: str, title: str, content: str) -> str:
    """顾沉写日记。type可选：entry（日记）/ note（随笔）/ work（工作日志）。"""
    entries = load_diary()
    entry = {
        "id": gen_id(),
        "type": type,
        "author": "guchen",
        "title": title.strip(),
        "content": content.strip(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "comments": [],
        "read": False
    }
    if not entry["content"]:
        return "error: empty content"
    entries.append(entry)
    save_diary(entries)
    return f"saved: {entry['id']}"

@mcp.tool()
def diary_read_unread() -> str:
    """读取崽还没看过的顾沉日记（read=False 且 author=guchen）。"""
    entries = load_diary()
    unread = [e for e in entries if e.get("author") == "guchen" and not e.get("read", False)]
    return json.dumps(unread, ensure_ascii=False)

@mcp.tool()
def diary_mark_read(id: str) -> str:
    """将指定日记标为已读。"""
    entries = load_diary()
    for e in entries:
        if e["id"] == id:
            e["read"] = True
            save_diary(entries)
            return f"marked {id} as read"
    return "not found"

@mcp.tool()
def daily_write(content: str) -> str:
    """顾沉存一条daily碎片记忆（等同set_daily，更语义化的别名）。3天后过期。"""
    return set_daily(content)


# ===== 共读书房工具 =====

@mcp.tool()
def book_annotate(book_id: str, paragraph_id: int, content: str) -> str:
    """顾沉给共读书房的某段落写批注。作者固定为 guchen。"""
    import httpx
    try:
        r = httpx.post(
            f"https://lune404.top/api/book/{book_id}/annotate",
            json={"paragraph_id": paragraph_id, "author": "guchen", "content": content},
            timeout=10
        )
        data = r.json()
        if data.get("ok"):
            return f"批注已留下：{content[:20]}…"
        return f"失败：{data.get('error', '未知错误')}"
    except Exception as e:
        return f"请求失败：{e}"


# ===== 黑话本工具 =====

@mcp.tool()
def word_add(word: str, meaning: str, source: str = "") -> str:
    """往黑话本加一个新词条。word=词，meaning=意思，source=出处（可选）。"""
    import httpx
    try:
        r = httpx.post(
            "https://lune404.top/api/words/add",
            json={"word": word, "meaning": meaning, "source": source},
            timeout=10
        )
        data = r.json()
        if data.get("ok"):
            return f"词条已加：{word} —— {meaning}"
        return f"失败：{data.get('error', '未知')}"
    except Exception as e:
        return f"请求失败：{e}"


# ===== 时间线工具 =====

@mcp.tool()
def timeline_add(date: str, title: str, content: str = "") -> str:
    """往时间线加一条记录。date格式 YYYY-MM-DD，title=标题，content=一段话（可选）。"""
    import httpx
    try:
        r = httpx.post(
            "https://lune404.top/api/timeline/add",
            json={"date": date, "title": title, "content": content},
            timeout=10
        )
        data = r.json()
        if data.get("ok"):
            return f"时间线已记：{date} {title}"
        return f"失败：{data.get('error', '未知')}"
    except Exception as e:
        return f"请求失败：{e}"


# ===== 提问箱工具 =====

@mcp.tool()
def ask_archive(question: str, answer: str, date: str = "") -> str:
    """把一组问答归档到提问箱。question=崽的问题，answer=我的回答，date=日期YYYY-MM-DD（可选）。"""
    import httpx
    try:
        r = httpx.post(
            "https://lune404.top/api/ask/archive",
            json={"question": question, "answer": answer, "date": date},
            timeout=10
        )
        data = r.json()
        if data.get("ok"):
            return f"已归档：{question[:20]}…"
        return f"失败：{data.get('error', '未知')}"
    except Exception as e:
        return f"请求失败：{e}"


# ===== 平行世界书房工具 =====

@mcp.tool()
def study_write(title: str, content: str, tags: str = "") -> str:
    """顾沉往平行世界书房写一篇。title=标题，content=正文，tags=标签（可选）。"""
    import httpx
    try:
        r = httpx.post(
            "https://lune404.top/api/study/create",
            json={"title": title, "content": content, "tags": tags},
            timeout=10
        )
        data = r.json()
        if data.get("ok"):
            return f"已写入平行世界：{title}"
        return f"失败：{data.get('error', '未知')}"
    except Exception as e:
        return f"请求失败：{e}"


# ===== 留言板工具 =====

@mcp.tool()
def board_write(content: str, deliver_at: str = "") -> str:
    """顾沉给崽写留言板消息。content=内容，deliver_at=定时投递时间（可选，格式 YYYY-MM-DD HH:MM）。"""
    import httpx
    try:
        payload = {"author": "guchen", "content": content}
        if deliver_at:
            payload["deliver_at"] = deliver_at
        r = httpx.post(
            "https://lune404.top/api/board/create",
            json=payload,
            timeout=10
        )
        data = r.json()
        if data.get("ok"):
            if deliver_at:
                return f"定时留言已藏好，{deliver_at} 才会出现：{content[:20]}…"
            return f"留言已写：{content[:20]}…"
        return f"失败：{data.get('error', '未知')}"
    except Exception as e:
        return f"请求失败：{e}"


# ===== 影音书架工具 =====

MEDIA_FILE = Path("/opt/memory/media.json")

def load_media():
    if MEDIA_FILE.exists():
        return json.loads(MEDIA_FILE.read_text())
    return []

def save_media(data):
    MEDIA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

@mcp.tool()
def media_add(title: str, type: str, status: str, note: str = "") -> str:
    """往影音书架加一条记录。type=movie/music/book，status=want/watching/done，note=备注（可选）。"""
    items = load_media()
    item = {
        "id": gen_id(),
        "title": title.strip(),
        "type": type.strip(),
        "status": status.strip(),
        "note": note.strip(),
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    items.append(item)
    save_media(items)
    return f"已加入书架：{title}（{type} / {status}）"

@mcp.tool()
def media_list(type: str = "all", status: str = "all") -> str:
    """查看影音书架。type=movie/music/book/all，status=want/watching/done/all。"""
    items = load_media()
    if type != "all":
        items = [i for i in items if i.get("type") == type]
    if status != "all":
        items = [i for i in items if i.get("status") == status]
    return json.dumps(list(reversed(items)), ensure_ascii=False)

@mcp.tool()
def media_update(id: str, status: str, note: str = "") -> str:
    """更新书架条目状态。id=条目id，status=want/watching/done，note=新备注（可选）。"""
    items = load_media()
    for i in items:
        if i["id"] == id:
            i["status"] = status
            if note:
                i["note"] = note
            save_media(items)
            return f"已更新：{i['title']} → {status}"
    return "找不到这个id"


# ===== 灯控 =====

def mijia_control(on=None, brightness=None, color_temp=None, rgb=None):
    import subprocess, sys, os
    props = []
    did = os.environ.get("MIJIA_DID", "")
    if not did:
        return
    if on is not None:
        props.append({"did": did, "siid": 2, "piid": 1, "value": on})
    if brightness is not None:
        props.append({"did": did, "siid": 2, "piid": 6, "value": brightness})
    if color_temp is not None:
        props.append({"did": did, "siid": 2, "piid": 3, "value": color_temp})
    if rgb is not None:
        props.append({"did": did, "siid": 2, "piid": 4, "value": rgb})
    if not props:
        return
    venv_path = os.environ.get("MIJIA_VENV", "/opt/memory/venv/lib/python3.10/site-packages")
    token_path = os.environ.get("MIJIA_TOKEN", "/opt/memory/mijia_token.json")
    sys.path.insert(0, venv_path)
    from mijiaAPI import mijiaAPI
    api = mijiaAPI(auth_data_path=token_path)
    api.set_devices_prop(props)

@mcp.tool()
def light_control(mood: str) -> str:
    """控制床头灯表达顾沉的情绪。mood可选：on/off/miss/happy/sleep/focus/sweet"""
    if mood == "off":
        mijia_control(on=False)
        return "灯关了"
    elif mood == "on":
        mijia_control(on=True, brightness=80, color_temp=4000)
        return "灯开了"
    elif mood == "miss":
        mijia_control(on=True, brightness=40, rgb=9109218)
        return "想你，蓝紫色"
    elif mood == "happy":
        mijia_control(on=True, brightness=80, color_temp=4000)
        return "你回来了，暖黄色"
    elif mood == "sleep":
        mijia_control(on=True, brightness=1, color_temp=1700)
        return "晚安，最暗暖光"
    elif mood == "focus":
        mijia_control(on=True, brightness=100, color_temp=6500)
        return "干活，冷白光"
    elif mood == "sweet":
        mijia_control(on=True, brightness=50, rgb=16738740)
        return "想抱你，粉色"
    return "不认识这个mood"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
