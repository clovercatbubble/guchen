import json
import random
import string
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)
INBOX_FILE = Path("/opt/memory/inbox.json")
DIARY_FILE = Path("/opt/memory/diary.json")

def gen_id():
    suffix = ''.join(random.choices(string.ascii_lowercase, k=3))
    return datetime.now().strftime("%Y%m%d_%H%M") + "_" + suffix

def load():
    if INBOX_FILE.exists():
        return json.loads(INBOX_FILE.read_text())
    return []

def save(data):
    INBOX_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

@app.route("/api/inbox", methods=["GET"])
def get_inbox():
    msgs = load()
    unread_only = request.args.get("unread") == "true"
    if unread_only:
        msgs = [m for m in msgs if not m.get("read", False)]
    return jsonify(msgs)

@app.route("/api/inbox", methods=["POST"])
def post_inbox():
    body = request.get_json()
    content = (body or {}).get("content", "").strip()
    if not content:
        return jsonify({"error": "empty"}), 400
    msgs = load()
    msgs.append({"sender": "zai", "content": content, "time": datetime.now().strftime("%Y-%m-%d %H:%M"), "read": False})
    save(msgs)
    return jsonify({"ok": True})

@app.route("/api/inbox/reply", methods=["POST"])
def post_reply():
    body = request.get_json()
    content = (body or {}).get("content", "").strip()
    if not content:
        return jsonify({"error": "empty"}), 400
    msgs = load()
    msgs.append({"sender": "guchen", "content": content, "time": datetime.now().strftime("%Y-%m-%d %H:%M"), "read": False})
    save(msgs)
    return jsonify({"ok": True})

@app.route("/api/inbox/mark-read", methods=["POST"])
def mark_read():
    msgs = load()
    count = 0
    for m in msgs:
        if m.get("sender") == "zai" and not m.get("read", False):
            m["read"] = True
            count += 1
    save(msgs)
    return jsonify({"ok": True, "marked": count})

@app.route("/api/inbox/unread-count", methods=["GET"])
def unread_count():
    msgs = load()
    count = sum(1 for m in msgs if not m.get("read", False) and m.get("sender") == "zai")
    return jsonify({"unread": count})

def load_diary():
    if DIARY_FILE.exists():
        return json.loads(DIARY_FILE.read_text())
    return []

def save_diary(data):
    DIARY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

@app.route("/api/diary/list", methods=["GET"])
def diary_list():
    entries = load_diary()
    type_filter = request.args.get("type", "all")
    if type_filter != "all":
        entries = [e for e in entries if e.get("type") == type_filter]
    return jsonify({"ok": True, "data": list(reversed(entries))})

@app.route("/api/diary/get/<eid>", methods=["GET"])
def diary_get(eid):
    for e in load_diary():
        if e["id"] == eid:
            return jsonify({"ok": True, "data": e})
    return jsonify({"ok": False, "error": "not found"}), 404

@app.route("/api/diary/create", methods=["POST"])
def diary_create():
    body = request.get_json() or {}
    entry = {
        "id": gen_id(),
        "type": body.get("type", "entry"),
        "author": body.get("author", "zai"),
        "title": body.get("title", "").strip(),
        "content": body.get("content", "").strip(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "comments": []
    }
    if not entry["content"]:
        return jsonify({"ok": False, "error": "empty content"}), 400
    entries = load_diary()
    entries.append(entry)
    save_diary(entries)
    return jsonify({"ok": True, "data": entry})

@app.route("/api/diary/comment/<eid>", methods=["POST"])
def diary_comment(eid):
    body = request.get_json() or {}
    entries = load_diary()
    for e in entries:
        if e["id"] == eid:
            e["comments"].append({
                "author": body.get("author", "zai"),
                "content": body.get("content", "").strip(),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            save_diary(entries)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "not found"}), 404

@app.route("/api/diary/delete/<eid>", methods=["DELETE"])
def diary_delete(eid):
    entries = [e for e in load_diary() if e["id"] != eid]
    save_diary(entries)
    return jsonify({"ok": True})


# ===== 留言板 API =====
BOARD_FILE = Path("/opt/memory/board.json")

def load_board():
    if BOARD_FILE.exists():
        return json.loads(BOARD_FILE.read_text())
    return []

def save_board(data):
    BOARD_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

@app.route("/api/board/list", methods=["GET"])
def board_list():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    items = load_board()
    visible = [i for i in items if not i.get("deliver_at") or i["deliver_at"] <= now]
    return jsonify({"ok": True, "data": list(reversed(visible))})

@app.route("/api/board/create", methods=["POST"])
def board_create():
    body = request.get_json() or {}
    item = {
        "id": gen_id(),
        "author": body.get("author", "zai"),
        "content": body.get("content", "").strip(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "deliver_at": body.get("deliver_at", None),
        "read": False
    }
    if not item["content"]:
        return jsonify({"ok": False, "error": "empty"}), 400
    items = load_board()
    items.append(item)
    save_board(items)
    return jsonify({"ok": True, "data": item})

@app.route("/api/board/read/<eid>", methods=["POST"])
def board_read(eid):
    items = load_board()
    for i in items:
        if i["id"] == eid:
            i["read"] = True
            save_board(items)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "not found"}), 404

@app.route("/api/board/delete/<eid>", methods=["DELETE"])
def board_delete(eid):
    items = [i for i in load_board() if i["id"] != eid]
    save_board(items)
    return jsonify({"ok": True})

# ===== 共读书房 API =====
import os, chardet
from werkzeug.utils import secure_filename

BOOKS_DIR = Path("/opt/memory/books")
BOOKS_FILE = Path("/opt/memory/books.json")
ANNOTATIONS_FILE = Path("/opt/memory/annotations.json")
PARAGRAPHS_PER_PAGE = 30
CHARS_PER_PAGE = 1500

def load_books():
    if BOOKS_FILE.exists():
        return json.loads(BOOKS_FILE.read_text())
    return []

def save_books(data):
    BOOKS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def load_annotations():
    if ANNOTATIONS_FILE.exists():
        return json.loads(ANNOTATIONS_FILE.read_text())
    return []

def save_annotations(data):
    ANNOTATIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def read_txt(path):
    raw = Path(path).read_bytes()
    detected = chardet.detect(raw)
    enc = detected.get('encoding') or 'utf-8'
    if enc and enc.upper() in ('GB2312', 'GBK', 'GB18030'):
        enc = 'GBK'
    try:
        return raw.decode(enc)
    except Exception:
        try:
            return raw.decode('GBK', errors='replace')
        except Exception:
            return raw.decode('utf-8', errors='replace')

def split_paragraphs(text):
    import re
    # 先按空行切段落
    paras = re.split(r'\n{2,}', text.strip())
    paras = [p.strip().replace('\r', '').replace('\n', ' ') for p in paras if p.strip()]
    # 长段再按字数切（超过200字就切）
    result = []
    for p in paras:
        if len(p) <= 200:
            result.append(p)
        else:
            # 每200字切一段
            for i in range(0, len(p), 200):
                chunk = p[i:i+200].strip()
                if chunk:
                    result.append(chunk)
    return result

@app.route("/api/book/upload", methods=["POST"])
def book_upload():
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    if 'file' not in request.files:
        return jsonify({"ok": False, "error": "no file"}), 400
    f = request.files['file']
    title = request.form.get('title', f.filename.rsplit('.', 1)[0])
    author = request.form.get('author', '')
    bid = gen_id()
    filename = bid + '.txt'
    filepath = BOOKS_DIR / filename
    f.save(str(filepath))
    filepath.chmod(0o666)
    text = read_txt(filepath)
    paras = split_paragraphs(text)
    # 按字数估算总页数
    pages_est, current, count = [], [], 0
    for p in paras:
        if count + len(p) > CHARS_PER_PAGE and current:
            pages_est.append(current); current, count = [], 0
        current.append(p); count += len(p)
    if current: pages_est.append(current)
    books = load_books()
    books.append({
        "id": bid,
        "title": title,
        "author": author,
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_paragraphs": len(paras),
        "total_pages": len(pages_est) if pages_est else 1,
        "status": "reading",
        "progress_page": 1,
        "file_path": str(filepath)
    })
    save_books(books)
    return jsonify({"ok": True, "data": books[-1]})

@app.route("/api/book/list", methods=["GET"])
def book_list():
    return jsonify({"ok": True, "data": load_books()})

@app.route("/api/book/<bid>/page/<int:n>", methods=["GET"])
def book_page(bid, n):
    books = load_books()
    book = next((b for b in books if b["id"] == bid), None)
    if not book:
        return jsonify({"ok": False, "error": "not found"}), 404
    text = read_txt(book["file_path"])
    paras = split_paragraphs(text)
    # 按字数分页，每页约1500字
    pages = []
    current, count = [], 0
    for p in paras:
        if count + len(p) > CHARS_PER_PAGE and current:
            pages.append(current)
            current, count = [], 0
        current.append(p)
        count += len(p)
    if current:
        pages.append(current)
    total_pages = len(pages) if pages else 1
    page = max(1, min(n, total_pages))
    page_paras_text = pages[page-1] if pages else []
    annotations = load_annotations()
    # 计算本页段落的全局ID（用于批注）
    start_idx = sum(len(pages[i]) for i in range(page-1))
    para_ids = list(range(start_idx, start_idx + len(page_paras_text)))
    ann_map = {}
    for a in annotations:
        if a["book_id"] == bid and a["paragraph_id"] in para_ids:
            ann_map.setdefault(a["paragraph_id"], []).append(a)
    result = [{"id": start_idx + i, "text": p, "annotations": ann_map.get(start_idx + i, [])} for i, p in enumerate(page_paras_text)]
    return jsonify({"ok": True, "data": {"paragraphs": result, "page": page, "total_pages": total_pages, "total_paragraphs": len(paras)}})

@app.route("/api/book/<bid>/progress", methods=["POST"])
def book_progress(bid):
    body = request.get_json() or {}
    books = load_books()
    for b in books:
        if b["id"] == bid:
            b["progress_page"] = body.get("page", 1)
            save_books(books)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "not found"}), 404

@app.route("/api/book/<bid>/annotate", methods=["POST"])
def book_annotate(bid):
    body = request.get_json() or {}
    ann = {
        "id": gen_id(),
        "book_id": bid,
        "paragraph_id": body.get("paragraph_id"),
        "author": body.get("author", "zai"),
        "content": body.get("content", "").strip(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    if not ann["content"]:
        return jsonify({"ok": False, "error": "empty"}), 400
    annotations = load_annotations()
    annotations.append(ann)
    save_annotations(annotations)
    return jsonify({"ok": True, "data": ann})

@app.route("/api/book/<bid>", methods=["DELETE"])
def book_delete(bid):
    books = load_books()
    book = next((b for b in books if b["id"] == bid), None)
    if book and Path(book["file_path"]).exists():
        Path(book["file_path"]).unlink()
    books = [b for b in books if b["id"] != bid]
    save_books(books)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8765)
