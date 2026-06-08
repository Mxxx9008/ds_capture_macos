# DeepSeek Capture

Mac + Android 设备环境下，抓取 DeepSeek App 聊天内容并生成结构化 JSON。

## 快速开始

```bash
# 1. 一次性初始化
pip install uiautomator2
python3 -m uiautomator2 init

# 2. 手机已连接 + USB 调试开启
adb devices

# 3. 文本抓取 (快速模式，默认)
cd ~/Desktop/deepseek_capture
python3 deepseek_capture.py "你的问题"

# 4. 专家模式 (深度思考)
python3 deepseek_capture.py "专家" "你的问题"

# 5. 文本 + URL 抓取 (需要 Frida + root)
python3 deepseek_capture.py "你的问题" --frida

# 输出: ~/Desktop/deepseek_capture_quick.json 或 deepseek_capture_expert.json
```

## 功能矩阵

| 功能 | 状态 | 说明 |
|------|:---:|------|
| AI 回答文本 | ✅ | 多节点合并 |
| 模型选择 (快速/专家) | ✅ | "专家" CLI 参数 |
| 新对话创建 | ✅ | 每次运行开启新对话 |
| 参考来源提取 | ✅ | 网页面板解析 (站点名+标题+日期) |
| 参考来源 URL | ✅ | Frida WebView hook (4/4 验证) |
| sitename 域名提取 | ✅ | URL 域名映射 |
| 参考内容 Summary | ❌ | 未实现 |

## 与豆包版本的差异

| 项目 | 豆包 | DeepSeek |
|------|------|----------|
| 包名 | `com.larus.nova` | `com.deepseek.chat` |
| Activity | ChatActivity + AliasActivity1 | MainActivity (单 Activity) |
| 回答格式 | 单个长文本节点 | 多个段落节点 |
| 参考引用 | 可展开卡片 `tv_reference_content` | 内联 `[citation:N]` + "N 个网页" 面板 |
| 模型选择 | 底部栏 toggle + 面板 | 主页文本标签页 |
| Resource ID | 有 (ll_reference_title 等) | 无，全靠 text/desc |
| 发送按钮 | `action_send` (resourceId) | `desc="发送"` |
| 输入框 | EditText 始终可见 | 点击底部区域后出现 |
| 思考模式 | "深度思考" toggle | 专家模式 + "深度思考" toggle |

## 目录结构

```
deepseek_capture/
├── README.md
├── deepseek_capture.py              # 主抓取脚本
├── frida_webview_url.js             # Frida WebView URL hook
└── docs/
    └── capture_summery.md           # 项目进度总结
```

## CLI

```bash
# 快速模式 (默认) — 支持智能搜索
python3 deepseek_capture.py "你的问题"

# 专家模式 (深度思考，无搜索)
python3 deepseek_capture.py "专家" "你的问题"

# URL 抓取 — 需 Frida + root
python3 deepseek_capture.py "你的问题" --frida

# 仅抓取当前屏幕（不发消息）
python3 deepseek_capture.py
```

## 输出格式

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "question": "推荐三个北京景点",
    "mode": "quick",
    "search_summary": "9 个网页",
    "search_sources": [
      {
        "index": 1,
        "title": "北京中轴线官网",
        "sitename": "北京旅游网",
        "url": "",
        "summary": "鼓楼化身时间博物馆..."
      }
    ],
    "answer": "故宫博物院...",
    "total_references": 9
  }
}
```

## 环境要求

- macOS
- Python 3.10+
- ADB + uiautomator2
- Android 设备 (Pixel 6 Pro 测试通过)

## 工作原理

### Level A: UI 文本提取

通过 `uiautomator2.dump_hierarchy()` 读取 UI 树，检测多节点 AI 回复文本并合并。DeepSeek 无 resource ID，全部通过 text/content-desc 选择器定位元素。

### Level B: Frida WebView URL 抓取

Frida hook `WebView.loadUrl()` 等 5 个 hook 拦截参考链接 URL。点击引用编号打开网页时捕获真实 URL。

## 踩坑记录

1. **无 resource ID** — DeepSeek 全 UI 通过 text/content-desc 标识，无法用 `d(resourceId=...)`
2. **多节点回答** — 回答被拆成多个 TextView 节点，需合并去重
3. **EditText 非始终可见** — 需先点击底部 hint 区域激活输入框
4. **发送按钮非可点击标记** — `clickable=false` 但 uiautomator2 仍可点击
5. **充电通知泄漏** — "正在充电，已完成百分之 N" 被混入答案文本
6. **专家模式不支持搜索** — 仅快速模式有 "智能搜索" 和网页引用
