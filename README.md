# DeepSeek Capture

> Mac + Android 设备环境下，自动化抓取 DeepSeek App 聊天内容（AI 回答 + 参考来源 + URL），输出结构化 JSON。

## 快速开始

```bash
# 1. 一次性环境初始化
pip install uiautomator2
python3 -m uiautomator2 init

# 2. 确认手机已连接 + USB 调试已开启
adb devices

# 3. 文本抓取（快速模式，默认）
cd ~/Desktop/deepseek_capture
python3 deepseek_capture.py "你的问题"

# 4. 专家模式（深度推理，无搜索）
python3 deepseek_capture.py "专家" "你的问题"

# 5. 文本 + URL 抓取（需 Frida + Magisk Root）
python3 deepseek_capture.py "你的问题" --frida
python3 deepseek_capture.py "专家" "你的问题" --frida
```

**输出文件：**
- 快速模式 → `~/Desktop/deepseek_capture_quick.json`
- 专家模式 → `~/Desktop/deepseek_capture_expert.json`

---

## 功能矩阵

| 功能 | 快速模式 | 专家模式 | 说明 |
|------|:---:|:---:|------|
| AI 回答文本 | ✅ | ✅ | 多节点合并去重 |
| 模型选择 | ✅ | ✅ | `"专家"` CLI 参数切换 |
| 新对话创建 | ✅ | ✅ | 每次运行自动开启全新对话 |
| 参考来源解析 | ✅ | ❌（无搜索） | citation badge 点击 + URL 捕获 |
| 参考来源 URL | ✅ `--frida` | N/A | Frida WebView Hook（5 个拦截点） |
| 参考来源站点名 | ✅ | N/A | URL 域名 → 站点名映射（50+ 条） |
| 参考来源标题 | ✅ | N/A | 从 AI 回答文本中提取 citation 所在句子 |
| 参考内容 Summary | ❌ | ❌ | 未实现 |

---

## CLI 完整用法

```bash
# 快速模式（文本 + 来源）
python3 deepseek_capture.py "你的问题"

# 快速模式 + URL 抓取
python3 deepseek_capture.py "你的问题" --frida

# 专家模式（纯推理，无联网搜索）
python3 deepseek_capture.py "专家" "你的问题"

# 专家模式 + URL（通常不需要，专家模式无搜索来源）
python3 deepseek_capture.py "专家" "你的问题" --frida

# 自定义输出路径
python3 deepseek_capture.py "你的问题" /path/to/output.json --frida

# 手动模式：仅抓取当前屏幕，不发送新消息
python3 deepseek_capture.py
python3 deepseek_capture.py --frida
```

---

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                   DeepSeek Capture                       │
│                   deepseek_capture.py (892 行)            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Level A: UI 文本提取                                     │
│  ┌──────────────┐   ┌────────────────┐   ┌────────────┐ │
│  │ uiautomator2 │ → │ dump_hierarchy │ → │ 文本合并    │ │
│  │ (UI 自动化)   │   │ (XML 树)       │   │ + 去重     │ │
│  └──────────────┘   └────────────────┘   └────────────┘ │
│                                                          │
│  Level A+: 模型选择 & 新对话                                │
│  ┌──────────────┐   ┌────────────────┐   ┌────────────┐ │
│  │ text/desc    │ → │ u2.click()    │ → │ 快速/专家   │ │
│  │ 选择器       │   │ + ADB tap      │   │ 模式切换    │ │
│  └──────────────┘   └────────────────┘   └────────────┘ │
│                                                          │
│  Level B: WebView URL 拦截                                │
│  ┌──────────────┐   ┌────────────────┐   ┌────────────┐ │
│  │ Frida 17.x   │ → │ WebView.loadUrl│ → │ URL 关联    │ │
│  │ (动态插桩)    │   │ + 4 个 hook    │   │ citation    │ │
│  └──────────────┘   └────────────────┘   └────────────┘ │
│                                                          │
│  输出: ~/Desktop/deepseek_capture_{mode}.json              │
└─────────────────────────────────────────────────────────┘
```

### Level A: UI 文本提取（无需 root）

通过 `uiautomator2.dump_hierarchy()` 读取 Android UI 树（XML），提取所有 `text` 和 `content-desc` 属性。DeepSeek 与豆包最大的不同是：**完全没有任何 resource-id**，所有 UI 交互全部通过文本内容（`text=""`）和辅助描述（`content-desc=""`）定位元素。

- **回答检测**：DeepSeek 将回答拆分为多个小 TextView 节点（段落、Tips、小节标题等），而非单个长文本。通过前后快照 diff + 多节点合并 + 连续去重拼接成完整回答。
- **流式检测**：每 2 秒检查一次答案长度，连续 4 次（8 秒）无增长则判定回答完成。
- **citation 定位**：使用 `content-desc="引用 N"` 精准定位每个引用标记，bounds 过滤（200 < y < 2800）排除顶部标题栏和底部输入栏干扰。

### Level B: Frida WebView URL 拦截（需 root + Frida）

通过 Frida 动态插桩 Hook Android WebView 的 5 个关键方法，在用户点击 citation badge 打开参考网页时捕获真实 URL。

**5 个 Hook 拦截点：**

| Hook | 目标方法 | 用途 |
|------|----------|------|
| 1 | `WebView.loadUrl(String)` | 主要 URL 加载入口 |
| 2 | `WebView.loadUrl(String, Map)` | 带 Header 的 URL 加载 |
| 3 | `WebViewClient.shouldOverrideUrlLoading` | URL 重定向拦截 |
| 4 | `Intent.getData` | Intent 跳转 URL |
| 5 | `URLSpan.onClick` | 富文本链接点击 |

**URL 捕获流程：**
1. 获取 AI 回答文本 → 正则提取所有 `[citation:N]` → 生成 citation 列表
2. 用 `content-desc="引用 N"` 定位每个 citation badge → ADB tap 点击
3. 等待 3 秒让 WebView 完全加载 → diff Frida 日志拿到新 URL
4. `adb shell input keyevent 4` 返回聊天页 → 继续下一个

---

## 输出 JSON 格式

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "task_id": "85085eaa985f",
    "question": "618最值得购买的家电推荐三个",
    "mode": "quick",
    "search_keywords": [],
    "search_sources": [
      {
        "index": 1,
        "title": "小户型留意统帅"冰立得"系列（占地小、容量大，同比增幅57%[citation:1]）",
        "sitename": "enorth",
        "url": "https://economy.enorth.com.cn/system/2026/06/05/059463113.shtml",
        "summary": "",
        "date": ""
      }
    ],
    "search_summary": "已阅读 9 个网页",
    "thinking_process": "",
    "answer": "…完整的 AI 回答文本…",
    "total_references": 7,
    "statistics": {
      "sitename_counts": {},
      "url_count": 3,
      "token_usage": {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tokens": 0
      }
    }
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 本次抓取唯一标识（12 位 hex） |
| `question` | string | 用户提问原文 |
| `mode` | string | `quick` / `expert` / `chat` |
| `search_summary` | string | 联网搜索摘要（如 "已阅读 9 个网页"） |
| `search_sources[].index` | int | citation 编号 |
| `search_sources[].title` | string | citation 所在句子（从回答中提取） |
| `search_sources[].sitename` | string | 来源站点名（URL 域名 → 中文名映射） |
| `search_sources[].url` | string | 参考网页真实 URL（需 `--frida`） |
| `search_sources[].date` | string | 来源发布日期（面板解析时可用） |
| `answer` | string | AI 完整回答文本 |
| `total_references` | int | 引用总数 |

---

## 项目结构

```
deepseek_capture/
├── deepseek_capture.py        # 主抓取脚本（892 行，25 个函数）
├── frida_webview_url.js        # Frida WebView URL Hook（5 个拦截点）
├── README.md                   # 本文件
├── docs/
│   └── capture_summery.md      # 项目进度总结
└── output/                     # 输出文件目录
```

---

## 工作原理

### 完整自动化流程

```
[1/6] 启动 Frida + DeepSeek
  ├── pkill 清理残留 Frida 进程
  ├── adb shell su 重启 frida-server（清除残留连接）
  ├── am force-stop + monkey 启动 DeepSeek
  ├── pidof 获取 PID（取首个，避免多 PID 报错）
  └── frida -D DEVICE -p PID 挂载 5 个 Hook

[2/5] 选择模型
  ├── text="快速模式"/"专家模式" 检测当前状态
  ├── 需要切换时：点击目标标签页
  └── 点击 "使用X模式开始对话" 进入聊天

[3/5] 快照 + 发送消息
  ├── dump_hierarchy() 获取当前屏幕文本（baseline）
  ├── 底部 ADB tap 激活 EditText
  ├── set_text() 输入问题
  └── desc="发送" 点击发送

[4/5] 等待 AI 回复
  ├── 每秒 dump_hierarchy() + 文本 diff
  ├── 多节点合并 + 去重（DeepSeek 拆段回答）
  ├── 连续 4 次（8s）无增长 → 判定完成
  └── 最长等待 240 秒

[5/6] 提取引用 + 捕获 URL
  ├── 正则提取答案中所有 [citation:N]
  ├── desc="引用 N" 定位 badge → ADB tap 点击
  ├── Frida 日志 diff 获取新 URL
  ├── title ← 正则从答案中提取 citation 所在句子
  ├── sitename ← URL 域名映射
  └── keyevent 4 返回聊天 → 继续下一个

[6/6] 保存 JSON
  └── json.dump() → ~/Desktop/deepseek_capture_{mode}.json
```

### DeepSeek 与豆包的 UI 差异

| 维度 | 豆包 (`doubao_capture`) | DeepSeek (`deepseek_capture`) |
|------|--------------------------|-------------------------------|
| **包名** | `com.larus.nova` | `com.deepseek.chat` |
| **Activity** | ChatActivity + AliasActivity1（双 Activity） | MainActivity（单 Activity） |
| **Resource ID** | 有（`ll_reference_title`、`input_text`、`action_send` 等） | **无**，全靠 text/content-desc |
| **回答格式** | 单个长文本节点 | 多个段落节点（需合并去重） |
| **引用格式** | 可展开卡片 `tv_reference_content` | 内联 `[citation:N]` + `desc="引用 N"` badge |
| **搜索引擎** | 始终联网 | 快速模式可联网，专家模式纯推理 |
| **输入框** | EditText 始终可见 | **需点击底部区域后才激活** |
| **发送按钮** | `resourceId="action_send"` | `desc="发送"` |
| **模型选择** | 底部栏 toggle → popup 面板 | 主页文本标签页 |
| **思考模式** | "深度思考" toggle | 专家模式（独立标签页） + "深度思考" toggle |
| **参考面板** | 点击展开卡片列表 | 点击 "已阅读 N 个网页" → 独立面板 **（点击面板按钮会导致 DeepSeek 崩溃退出）** |

---

## 踩坑记录

### 1. 无 Resource ID — 全部靠 text/desc 定位

DeepSeek 的 UI 层完全没有 `resource-id` 属性，无法使用 `d(resourceId="...")` 选择器。所有交互必须通过 `text`、`content-desc` 或 `className` 定位。

```python
# ❌ 豆包方式（不适用于 DeepSeek）
d(resourceId="com.deepseek.chat:id/action_send")

# ✅ DeepSeek 方式
d(description="发送")
d(text="发消息或按住说话")
d(className="android.widget.EditText")
```

### 2. 多节点回答合并

DeepSeek 将完整的 AI 回答拆分成数十个小 TextView 节点（每个段落、每个列表项、每个小标题都是一个独立节点）。需要从 `dump_hierarchy()` 中批量提取、合并、去重，同时排除系统通知和 UI 标签。

```python
# 合并逻辑：收集所有长度 ≥ 40 的候选文本
# 过滤掉底部按钮标签（"复制"、"喜欢"、"重新生成"等）
# 连续去重后 join('\n')
```

### 3. EditText 非始终可见

DeepSeek 的输入框在主页默认不显示。只有点击 "发消息或按住说话" 提示区域或直接用 ADB tap 底部位置后，EditText 才会出现。

```python
# 必须先激活输入框
_adb_tap(720, 2760)  # 点击屏幕底部中央
time.sleep(0.5)
edit = d(className="android.widget.EditText")
```

### 4. 面板按钮导致 App 崩溃

点击 "已阅读 N 个网页" 按钮会打开参考面板，但在部分情况下（尤其是 Frida 附加时）会导致 DeepSeek 进程退出。**最终方案：放弃面板，直接在聊天页面中点击 citation badge 获取 URL。**

### 5. Citation Badge 定位

citation badge 的 `text` 只是一个数字（如 "1"、"6"），在 UI 树中可能匹配到多处（段落编号、标题序号等）。用 `content-desc="引用 N"` 配合 bounds 范围过滤（200 < y < 2800）精准定位。

```python
# ✅ desc 选择器更精准
el = d(description=f"引用 {idx}")

# bounds 过滤排除顶部标题栏和底部工具栏
if 200 < top < 2800:
    _adb_tap(cx, cy)
```

### 6. WebView 返回后滚动位置丢失

每次从 WebView 按 back 回到聊天后，RecyclerView 的滚动位置会重置。下一个 citation badge 可能在当前屏幕外。

**解决：** 双向扫描 — 前 25 步向下滚动（`swipe 2200→400`），后 25 步向上滚动（`swipe 400→2200`）。每次扫描 50 步，确保覆盖整个回答内容。

### 7. Frida 连接稳定性

与豆包相同的问题：
- `pidof` 可能返回多个 PID → 取 `split()[0]`
- frida-server 残留连接 → 每次 attach 前 `killall` + 重启
- `shouldOverrideUrlLoading` 有多个重载 → 必须指定签名 `.overload('android.webkit.WebView', 'java.lang.String')`

### 8. 流式回答完成判定

DeepSeek 的专家模式生成时间可能超过 2 分钟。简单的 `detect + wait 5s` 不够可靠。

**解决：** 检测到答案后进入 "生长等待" 模式 — 每 2 秒检查一次文本长度，连续 4 次（8 秒）不再增长才判定完成，最多等待 50 秒（25 次检查）。

### 9. 充电通知泄漏

"正在充电，已完成百分之 N" 这种系统通知文本会被 `dump_hierarchy()` 抓取并混入答案。

**解决：** 在 `find_answer()` 的 `skip_words` 列表中加入 `"正在充电"、"已充满电"、"China Telecom"、"信号满格"` 等系统文本关键词。

### 10. 专家模式不支持搜索

DeepSeek 的专家模式（对应豆包的"思考模式"）是纯推理模式，不进行联网搜索。因此专家模式下 `search_sources` 始终为空，`total_references` 为 0 — 这是正常行为，不是 bug。

---

## 环境要求

| 组件 | 版本/说明 |
|------|----------|
| macOS | 开发与运行环境 |
| Python | 3.10+ |
| ADB | Android SDK Platform Tools |
| uiautomator2 | `pip install uiautomator2` |
| Frida | 17.9.11（Host + frida-server 版本一致） |
| Android 设备 | Pixel 6 Pro (Android 16)，需 Magisk Root（仅 Level B） |
| DeepSeek App | `com.deepseek.chat`，Google Play/官网 安装 |

---

## 故障排查

### Frida 启动失败

```bash
# 手动检查 frida-server 状态
adb shell "su -c 'ps -A | grep frida'"

# 手动重启
adb shell "su -c 'killall frida-server-17.9.11-android-arm64; nohup /data/local/tmp/frida-server-17.9.11-android-arm64 &'"

# 检查 Frida 版本一致性
frida --version
adb shell "su -c '/data/local/tmp/frida-server-17.9.11-android-arm64 --version'"
```

### 消息未发送

```bash
# 检查 DeepSeek 是否在前台
adb shell dumpsys window | grep mCurrentFocus
# 应显示: com.deepseek.chat/.MainActivity

# 手动启动
adb shell monkey -p com.deepseek.chat 1
```

### URL 捕获率低

- 确认 `--frida` 参数已加
- 确认手机已 root 且 frida-server 正在运行
- DeepSeek 版本更新可能导致 citation badge 的 content-desc 格式变化，检查 `adb shell uiautomator dump` 确认

---

## 相关项目

- **豆包抓取**: `doubao_capture` — 同架构，适配豆包 App（`com.larus.nova`）
- **Frida Hook 脚本**: `frida_webview_url.js` — 5 个 WebView 拦截 Hook，两个项目共用同一设计

---

## License

MIT
