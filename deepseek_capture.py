#!/usr/bin/env python3
"""
Capture DeepSeek chat — fully automated.
Send a message → wait for AI reply → save structured JSON.

Usage:
  python3 deepseek_capture.py "你的问题"                    # 快速模式 (default)
  python3 deepseek_capture.py "专家" "你的问题"              # 专家模式
  python3 deepseek_capture.py "你的问题" --frida             # with URL capture
  python3 deepseek_capture.py "专家" "问题" --frida          # 专家 + URL
  python3 deepseek_capture.py "问题" /path/to/out.json --frida
  python3 deepseek_capture.py --frida                        # manual capture

Setup (one-time):
  pip install uiautomator2
  python3 -m uiautomator2 init
"""

import subprocess
import time
import json
import os
import re
import sys
import secrets
import html as _html

# ── uiautomator2 ──────────────────────────────────────────────
try:
    import uiautomator2 as u2
    _HAS_U2 = True
except ImportError:
    _HAS_U2 = False

# ── Configuration ──────────────────────────────────────────────
ADB = os.path.expanduser("~/Library/Android/sdk/platform-tools/adb")
DEVICE = "19161FDEE0J82D"
OUTPUT = os.path.expanduser("~/Desktop/deepseek_capture.json")
TIMEOUT = 240
PACKAGE = "com.deepseek.chat"

# ── Frida WebView URL hook ─────────────────────────────────────
FRIDA_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "frida_webview_url.js")
_frida_proc = None
_frida_output = "/tmp/frida_deepseek_output.txt"


def _start_frida():
    """Launch Frida with WebView hook script against DeepSeek."""
    global _frida_proc

    subprocess.run(["pkill", "-9", "-f", "frida.*deepseek"], capture_output=True)
    time.sleep(0.5)
    subprocess.run([ADB, "-s", DEVICE, "shell",
                    "su", "-c", "killall frida-server-17 2>/dev/null; true"],
                   capture_output=True)
    time.sleep(0.5)
    subprocess.run([ADB, "-s", DEVICE, "shell",
                    "su", "-c", "nohup /data/local/tmp/frida-server-17 &"],
                   capture_output=True)
    time.sleep(1.5)

    subprocess.run([ADB, "-s", DEVICE, "shell", "am", "force-stop", PACKAGE],
                   capture_output=True)
    time.sleep(1.5)
    subprocess.run([ADB, "-s", DEVICE, "shell", "monkey", "-p", PACKAGE, "1"],
                   capture_output=True)
    time.sleep(6)
    _ensure_unlocked()

    pid = ""
    for attempt in range(3):
        result = subprocess.run([ADB, "-s", DEVICE, "shell", "pidof", PACKAGE],
                                capture_output=True, text=True)
        pid = result.stdout.strip().split()[0] if result.stdout.strip() else ""
        if pid:
            break
        time.sleep(2)

    if not pid:
        print("  [!] App didn't start after 3 attempts")
        return False

    with open(_frida_output, 'w') as f:
        _frida_proc = subprocess.Popen(
            ["frida", "-D", DEVICE, "-p", pid, "-l", FRIDA_SCRIPT],
            stdout=f, stderr=subprocess.STDOUT
        )

    for _ in range(15):
        time.sleep(1)
        try:
            with open(_frida_output) as f:
                content = f.read()
                if 'All hooks installed' in content:
                    global _d
                    _d = None  # Reset after app restart
                    return True
                if 'Process terminated' in content or 'Failed to load script' in content:
                    print("  [!] Frida attach failed")
                    return False
        except Exception:
            pass
    return False


def _stop_frida():
    global _frida_proc
    if _frida_proc:
        _frida_proc.terminate()
        try:
            _frida_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _frida_proc.kill()
        _frida_proc = None


def _read_frida_output():
    try:
        with open(_frida_output) as f:
            return f.read()
    except Exception:
        return ""


def _parse_new_urls(baseline_text, new_text):
    old_urls = set(re.findall(
        r'\[WebView\.loadUrl\] (?!javascript:)(.+?)(?:\n|$)',
        baseline_text
    ))
    new_urls = re.findall(
        r'\[WebView\.loadUrl\] (?!javascript:)(.+?)(?:\n|$)',
        new_text
    )
    return [u for u in new_urls
            if u not in old_urls and 'seclink.bytedance.com' not in u]


# ── uiautomator2 handle ────────────────────────────────────────
_d = None


def _get_d():
    global _d
    if _d is None:
        if not _HAS_U2:
            print("[!] uiautomator2 not installed.")
            sys.exit(1)
        _d = u2.connect(DEVICE)
    # Verify connection is alive
    try:
        _d.info
    except Exception:
        _d = u2.connect(DEVICE)
    return _d


# ── ADB input helpers ──────────────────────────────────────────

def _adb_swipe(x1, y1, x2, y2, duration_ms=200):
    subprocess.run(
        [ADB, "-s", DEVICE, "shell", "input", "swipe",
         str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
        capture_output=True)


def _adb_tap(x, y):
    subprocess.run(
        [ADB, "-s", DEVICE, "shell", "input", "tap", str(x), str(y)],
        capture_output=True)


# ── UI helpers ─────────────────────────────────────────────────

def _ensure_unlocked():
    subprocess.run([ADB, "-s", DEVICE, "shell", "wm", "dismiss-keyguard"],
                   capture_output=True)
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "swipe",
                    "540", "2900", "540", "100", "500"],
                   capture_output=True)
    time.sleep(1)


def _element_center(el):
    """Get (cx, cy) of a uiautomator2 element."""
    info = el.info
    bounds = info.get('bounds', {})
    cx = (bounds.get('left', 0) + bounds.get('right', 0)) // 2
    cy = (bounds.get('top', 0) + bounds.get('bottom', 0)) // 2
    return cx, cy


def restart_app():
    """Restart DeepSeek for clean state."""
    subprocess.run([ADB, "-s", DEVICE, "shell", "am", "force-stop", PACKAGE],
                   capture_output=True, text=True)
    time.sleep(1.5)
    subprocess.run([ADB, "-s", DEVICE, "shell", "monkey", "-p", PACKAGE,
                    "-c", "android.intent.category.LAUNCHER", "1"],
                   capture_output=True, text=True)
    time.sleep(5)
    _ensure_unlocked()
    global _d
    _d = None


def get_texts():
    """Extract visible text from uiautomator2 hierarchy dump."""
    global _d
    for attempt in range(3):
        try:
            d = _get_d()
            raw = d.dump_hierarchy()
            break
        except Exception:
            _d = None
            if attempt == 2:
                raise
            time.sleep(2)

    texts = re.findall(r'text="([^"]*)"', raw)
    descs = re.findall(r'content-desc="([^"]*)"', raw)
    result = []
    seen = set()
    for t in texts:
        t = _html.unescape(t).strip()
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    for desc in descs:
        desc = _html.unescape(desc).strip()
        if desc and desc not in seen:
            seen.add(desc)
            result.append(desc)
    return result


# ── Answer detection (DeepSeek-specific) ──────────────────────

def find_answer(before, after, question=""):
    """Detect AI answer from DeepSeek's multi-node response format.

    DeepSeek renders responses as multiple text nodes (paragraphs, tips,
    section headers). We merge candidate nodes and return the combined text.
    """
    before_set = set(before)
    skip_words = [
        "快速模式", "专家模式", "使用快速模式", "使用专家模式",
        "深度思考", "智能搜索", "上传文件", "切换至语音",
        "发消息或按住说话", "发消息", "发送", "取消",
        "打开侧边栏", "开启新对话", "关闭侧边栏", "关闭",
        "擅长复杂问题", "适合日常对话", "暂无对话",
        "搜索对话内容", "搜索结果", "引用", "网页",
        "暂无相关结果", "正在充电", "已充满电",
        "China Telecom", "中国电信", "信号满格",
        "USB 调试", "点按即可", "Android 系统通知",
    ]
    # Collect response nodes (DeepSeek splits answer across many text nodes)
    candidates = []
    for t in after:
        t = t.strip()
        if not t or t in before_set:
            continue
        if t == question:
            continue
        if any(w in t for w in skip_words) and len(t) < 20:
            continue
        # Skip short UI labels, dates, citation numbers
        if re.match(r'^\d{1,2}:\d{2}$', t):
            continue
        if re.match(r'^\d{1,2}$', t):
            continue
        if re.match(r'^\d{4}/\d{2}/\d{2}$', t):
            continue
        if re.match(r'^\d+$', t):  # bare citation numbers
            continue
        # DeepSeek response nodes: meaningful content > 15 chars
        if len(t) >= 15:
            candidates.append(t)

    if not candidates:
        return None

    # Merge nodes into a single answer, separated by newlines
    # Remove consecutive duplicates (scrolling can duplicate text)
    deduped = []
    for c in candidates:
        if not deduped or c != deduped[-1]:
            deduped.append(c)

    answer = "\n".join(deduped)
    return answer if len(answer) >= 40 else None


# ── Reference extraction (DeepSeek-specific) ───────────────────

def extract_search_info(texts):
    """Extract web search summary and ref count from visible text.

    DeepSeek shows inline citations like [citation:1] and a "N 个网页"
    button that opens a reference panel with source details.
    """
    search_summary = ""
    for t in texts:
        m = re.search(r'(\d+)\s*个网页', t)
        if m:
            search_summary = t
            break

    total_refs = 0
    all_citations = re.findall(r'\[citation:(\d+)\]', ' '.join(texts))
    if all_citations:
        total_refs = max(int(c) for c in all_citations)

    return search_summary, total_refs


def capture_refs_with_urls(answer_text="", use_frida=False):
    """Extract citation references from answer text + capture URLs via Frida.

    DeepSeek uses inline [citation:N] markers. We parse citations from the
    answer, then (if Frida) scroll to find and click each citation link
    to trigger WebView loading for URL capture.

    Returns (sources, captured_urls).
    """
    sources = []
    captured_urls = []

    # Extract unique citation numbers from answer
    citations = set()
    for m in re.finditer(r'\[citation:(\d+)\]', answer_text):
        citations.add(int(m.group(1)))

    if not citations:
        return sources, captured_urls

    # Build source list
    for c in sorted(citations):
        sources.append({
            "index": c,
            "title": "",
            "sitename": "",
            "url": "",
            "summary": "",
            "date": "",
        })

    print(f"  [*] {len(sources)} citations found in answer")

    if not use_frida:
        return sources, captured_urls

    # Click citation badges in answer body to trigger WebView.
    # Panel approach is unreliable (crashes DeepSeek).
    d = _get_d()
    baseline = _read_frida_output()

    for src in sources:
        idx = src["index"]

        d = _get_d()
        badge_found = False

        # Search for this badge. Citations appear top→bottom in answer text.
        # We scan down from current position — citation order maps to text order.
        for scroll_step in range(50):
            d = _get_d()
            # Citation badge: text="N" + content-desc="引用 N"
            el = d(description=f"引用 {idx}")
            if not el.exists:
                el = d(text=str(idx))
            if el.exists:
                for ei in range(min(el.count, 30)):
                    try:
                        info = el[ei].info
                        top = info.get('bounds', {}).get('top', 0)
                        if 200 < top < 2800:
                            bounds = info.get('bounds', {})
                            cx = (bounds.get('left', 0) + bounds.get('right', 0)) // 2
                            cy = (bounds.get('top', 0) + bounds.get('bottom', 0)) // 2
                            _adb_tap(cx, cy)
                            time.sleep(3)

                            new_output = _read_frida_output()
                            new_urls = _parse_new_urls(baseline, new_output)
                            url = new_urls[0] if new_urls else ""
                            captured_urls.append(url)
                            baseline = new_output
                            badge_found = True
                            print(f"    [{idx}] {'URL ✓' if url else 'no URL'}")
                            break
                    except Exception:
                        continue
            if badge_found:
                break
            # First 25 steps: scroll down. Last 25: scroll up (badge may be above)
            if scroll_step < 25:
                _adb_swipe(540, 2200, 540, 400, 200)
            else:
                _adb_swipe(540, 400, 540, 2200, 200)
            time.sleep(0.2)

        if badge_found:
            # Back from WebView, wait for chat restore
            subprocess.run([ADB, "-s", DEVICE, "shell", "input", "keyevent", "4"],
                           capture_output=True)
            time.sleep(3)
            _ensure_unlocked()
            global _d
            _d = None  # Fresh u2 connection
        else:
            captured_urls.append("")
            print(f"    [{idx}] badge not found")

    # Fill source info from URL domains
    for i, src in enumerate(sources):
        if i < len(captured_urls) and captured_urls[i]:
            src["url"] = captured_urls[i]
            if not src.get("sitename"):
                src["sitename"] = _parse_sitename_from_url(captured_urls[i])
        # Extract title from answer text: find sentence containing [citation:N]
        if not src.get("title"):
            pattern = rf'([^。.!！\n]{{5,80}}\[citation:{src["index"]}\][^。.!！\n]{{0,30}})'
            m = re.search(pattern, answer_text)
            if m:
                src["title"] = m.group(1).strip()

    print(f"  [*] {sum(1 for u in captured_urls if u)}/{len(captured_urls)} URLs captured")


    return sources, captured_urls


# ── Domain → sitename mapping ──────────────────────────────────

_DOMAIN_SITENAME_MAP = {
    "iesdouyin.com": "抖音", "douyin.com": "抖音",
    "m.toutiao.com": "今日头条", "toutiao.com": "今日头条",
    "m.weibo.cn": "微博", "weibo.com": "微博",
    "36kr.com": "36氪", "zhihu.com": "知乎",
    "bilibili.com": "哔哩哔哩",
    "xinhuanet.com": "新华网", "people.com.cn": "人民网",
    "gmw.cn": "光明网", "huanqiu.com": "环球网",
    "chinanews.com": "中国新闻网", "china.com.cn": "中国网",
    "youth.cn": "中国青年网", "ifeng.com": "凤凰网",
    "sina.com.cn": "新浪", "sina.com": "新浪",
    "qq.com": "腾讯新闻", "163.com": "网易新闻",
    "sohu.com": "搜狐", "thepaper.cn": "澎湃新闻",
    "csdn.net": "CSDN", "gov.cn": "中国政府网",
    "cctv.com": "央视网", "stdaily.com": "科技日报",
    "ctrip.com": "携程", "trip.com": "Trip.com",
    "klook.cn": "Klook客路", "klook.com": "Klook客路",
    "qunar.com": "去哪儿", "mafengwo.cn": "马蜂窝",
    "dianping.com": "大众点评", "meituan.com": "美团",
    "wikipedia.org": "维基百科", "baidu.com": "百度",
    "bjta.gov.cn": "北京旅游网",
}


def _parse_sitename_from_url(url):
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        domain = re.sub(r'^www\.', '', domain)
        domain = re.sub(r'^m\.', '', domain)
        for key, name in _DOMAIN_SITENAME_MAP.items():
            if domain == key or domain.endswith('.' + key):
                return name
        parts = domain.split('.')
        if len(parts) >= 2:
            return parts[-2] if parts[-2] not in ('com', 'co', 'org', 'net') else (
                parts[-3] if len(parts) >= 3 else parts[-2])
    except Exception:
        pass
    return ""


# ── Model + toggle management ──────────────────────────────────

def _select_model(mode):
    """Select 'quick' or 'expert' mode on DeepSeek main page.

    DeepSeek shows mode tabs on the main page:
    - '快速模式' (quick) - for daily chat
    - '专家模式' (expert/deep think) - for complex problems
    """
    d = _get_d()

    quick_tab = d(text="快速模式")
    expert_tab = d(text="专家模式")
    use_quick_text = d(text="使用快速模式开始对话")
    use_expert_text = d(text="使用专家模式开始对话")

    if mode == "quick":
        if use_quick_text.exists:
            print("[*] Model: already 快速模式")
            _ensure_search_enabled()
            return True
        if not quick_tab.exists:
            print("[!] Cannot find 快速模式 tab")
            return False
        quick_tab.click()
        time.sleep(0.5)
        d2 = _get_d()
        if d2(text="使用快速模式开始对话").exists:
            print("[*] Model switched to: quick")
            _ensure_search_enabled()
            return True
    elif mode == "expert":
        if use_expert_text.exists:
            print("[*] Model: already 专家模式")
            _ensure_deep_think_enabled()
            return True
        if not expert_tab.exists:
            print("[!] Cannot find 专家模式 tab")
            return False
        expert_tab.click()
        time.sleep(0.5)
        d2 = _get_d()
        if d2(text="使用专家模式开始对话").exists:
            print("[*] Model switched to: expert")
            _ensure_deep_think_enabled()
            return True

    print(f"[!] Model switch to {mode} may have failed")
    return False


def _ensure_search_enabled():
    """Enable smart search toggle in quick mode if available."""
    d = _get_d()
    search_btn = d(text="智能搜索")
    if not search_btn.exists:
        return
    # Check if already enabled - look for "已开启" or similar
    # For now, just leave it as-is (user typically enables it)
    pass


def _ensure_deep_think_enabled():
    """Enable deep think toggle in expert mode."""
    d = _get_d()
    think_btn = d(text="深度思考")
    if not think_btn.exists:
        return
    # The toggle state is not visible from text alone
    # User-specified: expert mode = deep think on
    # Just ensure the button is there (DeepSeek enables it by default in expert mode)
    pass


# ── Input flow (DeepSeek-specific) ────────────────────────────

def _start_new_conversation():
    """Start a fresh chat. DeepSeek uses '开启新对话' in top bar."""
    d = _get_d()

    # Click "开启新对话" button
    new_btn = d(description="开启新对话")
    if not new_btn.exists:
        new_btn = d(text="开启新对话")
    if new_btn.exists:
        _adb_tap(*_element_center(new_btn))
        time.sleep(1)
        return True

    # Fallback: close sidebar if open, then try again
    close_sidebar = d(description="关闭侧边栏")
    if close_sidebar.exists:
        close_sidebar.click()
        time.sleep(0.5)
        new_btn = d(description="开启新对话")
        if new_btn.exists:
            _adb_tap(*_element_center(new_btn))
            time.sleep(1)
            return True

    print("  [!] Could not find '开启新对话'")
    return False


def _activate_input():
    """Activate the chat input area and return the EditText element."""
    d = _get_d()

    # First check: is the EditText already visible?
    edit = d(className="android.widget.EditText")
    if edit.exists:
        bt = edit.info.get('bounds', {})
        edit_top = bt.get('top', 0)
        # Only use if it's in the bottom half (actual chat input, not search bar)
        if edit_top > 1500:
            return edit

    # Tap the hint text area to activate input
    hint = d(text="发消息或按住说话")
    if hint.exists:
        bounds = hint.info.get('bounds', {})
        cx = (bounds.get('left', 0) + bounds.get('right', 0)) // 2
        cy = (bounds.get('top', 0) + bounds.get('bottom', 0)) // 2
        _adb_tap(cx, cy)
        time.sleep(0.5)

    # Or tap bottom center
    if not d(className="android.widget.EditText").exists:
        _adb_tap(720, 2760)
        time.sleep(0.5)

    return d(className="android.widget.EditText")


def _click_send():
    """Click the send button (desc='发送')."""
    d = _get_d()
    send_btn = d(description="发送")
    if send_btn.exists:
        try:
            send_btn.click()
            return True
        except Exception:
            pass
    # Fallback: use keyboard enter
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "keyevent", "66"],
                   capture_output=True)
    return True


def send_message(text):
    """Type and send a message in DeepSeek."""
    print(f"[*] Sending: {text[:80]}{'...' if len(text) > 80 else ''}")
    _ensure_unlocked()

    edit = _activate_input()
    if not edit or not edit.exists:
        print("[!] Cannot find input field")
        return False

    edit.click()
    time.sleep(0.2)
    edit.set_text(text)
    time.sleep(0.3)
    _click_send()
    time.sleep(0.3)
    print("[*] Sent ✓")
    return True


# ── Response detection ─────────────────────────────────────────

def wait_for_response(before, timeout=TIMEOUT, question=""):
    """Wait for AI response. Returns (answer, search_summary, total_refs)."""
    search_summary = ""
    total_refs = 0

    for i in range(timeout):
        time.sleep(1)

        after = get_texts()

        # Check for search summary
        s, tr = extract_search_info(after)
        if s and not search_summary:
            search_summary, total_refs = s, tr

        ans = find_answer(before, after, question=question)
        if ans:
            if not search_summary:
                s, tr = extract_search_info(after)
                if s:
                    search_summary, total_refs = s, tr
            # DeepSeek streams progressively — wait + scroll to capture full answer
            no_growth = 0
            for _ in range(25):
                time.sleep(2)
                after2 = get_texts()
                ans2 = find_answer(before, after2, question=question)
                if ans2 and len(ans2) > len(ans):
                    ans = ans2
                    no_growth = 0
                else:
                    no_growth += 1
                    if no_growth >= 4:  # 4 checks (8s) with no growth = done
                        break
            return ans, search_summary, total_refs

        if i % 10 == 0 and i > 0:
            print(f"    ... {i}s")

    return None, "", 0


# ── Save output ────────────────────────────────────────────────

def save(question, answer, path=OUTPUT, search_summary="", total_references=0,
         sources=None, captured_urls=None, think_mode="quick"):
    if sources is None:
        sources = []
    if captured_urls is None:
        captured_urls = []

    # Populate URLs into sources
    for i, src in enumerate(sources):
        if i < len(captured_urls) and captured_urls[i]:
            src["url"] = captured_urls[i]
        # Fallback: extract sitename from URL domain
        if not src.get("sitename") and src.get("url"):
            src["sitename"] = _parse_sitename_from_url(src["url"])

    task_id = secrets.token_hex(6)
    mode = think_mode

    data = {
        "code": 0,
        "msg": "success",
        "data": {
            "task_id": task_id,
            "question": question,
            "mode": mode,
            "search_keywords": [],
            "search_sources": sources,
            "search_summary": search_summary,
            "thinking_process": "",
            "answer": answer,
            "total_references": total_references if total_references else len(sources),
            "statistics": {
                "sitename_counts": {},
                "url_count": len([s for s in sources if s.get("url")]),
                "token_usage": {
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_tokens": 0
                }
            }
        }
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    url_count = len([s for s in sources if s.get("url")])
    print(f"[*] Saved → {path}  ({url_count}/{len(sources)} URLs captured)")


# ── CLI ────────────────────────────────────────────────────────

def main():
    use_frida = "--frida" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    # Parse model mode: "专家" or "expert" as first positional arg
    MODEL_NAMES = {"专家": "expert", "expert": "expert"}
    think_mode = "quick"

    if len(args) > 0 and args[0] in MODEL_NAMES:
        think_mode = MODEL_NAMES[args[0]]
        msg = args[1] if len(args) > 1 else None
        out = args[2] if len(args) > 2 else OUTPUT
    else:
        msg = args[0] if len(args) > 0 else None
        out = args[1] if len(args) > 1 else OUTPUT

    # Generate mode-specific output filename
    if out == OUTPUT:
        suffix = f"_{think_mode}"
        out = OUTPUT.replace(".json", f"{suffix}.json")

    # ── Manual capture mode ──
    if msg is None:
        print("=" * 55)
        mode_label = "Frida" if use_frida else "Text-only"
        print(f"  Mode: Capture only ({mode_label})")
        print(f"  Model: {think_mode}")
        print(f"  Output: {out}")
        print("=" * 55)

        if use_frida:
            print("[*] Starting Frida...")
            if not _start_frida():
                print("[!] Frida failed, falling back to text-only")
                use_frida = False
            else:
                print("[*] Frida ready")
                time.sleep(3)

        texts = get_texts()
        answer = find_answer(set(), texts)
        if answer:
            print(f"\n{'─' * 50}")
            print(answer[:500])
            print(f"{'─' * 50}\n")
            sources, captured_urls = capture_refs_with_urls(
                answer_text=answer, use_frida=use_frida)
            search_summary, _ = extract_search_info(texts)
            total_refs = len(sources) if sources else 0
            save("(manual)", answer, out, search_summary, total_refs,
                 sources, captured_urls, think_mode=think_mode)
            print("Done ✓")
        else:
            print("[!] No AI response visible.")
        if use_frida:
            _stop_frida()
        return

    # ── Automated send + capture ──
    print("=" * 55)
    mode_label = "Frida" if use_frida else "Text-only"
    print(f"  Message: {msg}")
    print(f"  Output:  {out}")
    print(f"  Model:   {think_mode}")
    print(f"  Mode:    {mode_label}")
    print("=" * 55)

    if use_frida:
        print("[1/6] Start Frida + DeepSeek...")
        if not _start_frida():
            print("[!] Frida failed — falling back to text-only")
            use_frida = False
            print("[1/5] Restart app (clean state)...")
            restart_app()
        else:
            print("[*] Frida ready, hooks active")
            time.sleep(3)
            global _d
            _d = None
    else:
        print("[1/5] Restart app (clean state)...")
        restart_app()

    print("[2/5] Select model + new conversation...")
    _select_model(think_mode)
    # Tap "使用X模式开始对话" to enter chat, or use "开启新对话"
    d = _get_d()
    start_text = d(text="使用快速模式开始对话") if think_mode == "quick" else d(text="使用专家模式开始对话")
    if start_text.exists:
        start_text.click()
        time.sleep(2)
    else:
        _start_new_conversation()
        time.sleep(1)
    # Verify we're in a chat (EditText should be visible or activatable)
    d = _get_d()
    if not d(className="android.widget.EditText").exists:
        # Try bottom tap to activate input
        _adb_tap(720, 2760)
        time.sleep(1)

    print("[3/5] Snapshot + send...")
    before = set(get_texts())
    send_message(msg)

    step = "6" if use_frida else "5"
    print(f"[5/{step}] Wait for AI reply...")
    answer, search_summary, total_refs = wait_for_response(
        before, question=msg
    )

    if answer:
        print(f"\n{'─' * 50}")
        print(answer[:500])
        if len(answer) > 500:
            print(f"... ({len(answer)} chars total)")
        print(f"{'─' * 50}\n")

        # Extract references + URLs in one combined step
        print(f"[6/{step}] Extract references + capture URLs...")
        time.sleep(2)  # Wait for reference button to fully render
        sources, captured_urls = capture_refs_with_urls(
            answer_text=answer, use_frida=use_frida)

        captured = len([u for u in captured_urls if u])
        print(f"  Result: {len(sources)} sources, {captured}/{len(sources)} URLs")
        if not search_summary:
            search_summary2, _ = extract_search_info(get_texts())
            if search_summary2:
                search_summary = search_summary2

        final_step = "7" if use_frida else "6"
        print(f"[{final_step}/{final_step}] Save JSON...")
        save(msg, answer, out, search_summary, total_refs if total_refs else len(sources),
             sources, captured_urls, think_mode=think_mode)
        print("Done ✓")
    else:
        print("[!] Timeout — no AI response detected.")

    if use_frida:
        _stop_frida()


if __name__ == "__main__":
    main()
