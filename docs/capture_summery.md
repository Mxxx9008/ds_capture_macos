# DeepSeek 抓包项目进度总结

> 更新时间: 2026-06-08

## 总体进度

```
████████████████░░░░  80%

已解决 ✅
├── AI 回答文本提取 ✅
├── 模型选择 (快速/专家) ✅
├── 新对话创建 ✅
├── 参考来源提取 ✅ (网页面板: 站点名+标题+日期)
├── 参考来源 URL ✅ (Frida 4/4 验证)
├── sitename 域名提取 ✅
├── Frida WebView Hook ✅
├── uiautomator2 自动化 ✅
├── 手机锁屏自动解除 ✅
└── 系统通知过滤 ✅

未完成 ❌
└── 参考内容 Summary ❌
```

## 一、已实现

### 1. 快速模式 (AI 回答 + 搜索引用)
- 默认模式，支持智能搜索 (联网)
- 回答格式：多节点合并
- 引用格式：内联 `[citation:N]` + "N 个网页" 面板
- 源信息：站点名、标题、日期、摘要

### 2. 专家模式 (深度思考)
- `python3 deepseek_capture.py "专家" "问题"`
- 无搜索功能，纯推理
- 回答更长、更深入
- "深度思考" toggle 默认启用

### 3. 模型切换
- 快速模式 ↔ 专家模式
- 通过主页文本标签页切换
- 自动检测当前模式避免重复切换

### 4. 新对话创建
- 每次运行创建全新对话
- 通过 "开启新对话" 按钮 (desc)

## 二、与豆包版本的功能对比

| 功能 | 豆包 | DeepSeek |
|------|:---:|:---:|
| 回答文本 | ✅ | ✅ |
| 模型选择 | ✅ (快速/思考) | ✅ (快速/专家) |
| 新对话 | ✅ | ✅ |
| 参考标题 | ✅ | ✅ |
| 参考站点名 | ✅ | ✅ |
| 参考 URL | ✅ | ⚠️ 待验证 |
| Summary | ❌ | ❌ |
| 回答格式 | 单长文本 | 多节点合并 |

## 三、环境

| 组件 | 状态 |
|------|------|
| Pixel 6 Pro (Android 16) | ✅ 测试设备，Magisk root |
| ADB | ✅ |
| Frida 17.9.11 | ⚠️ 待调试 |
| uiautomator2 | ✅ |
| DeepSeek App | ✅ com.deepseek.chat |

## 四、命令行

```bash
# 快速模式
cd ~/Desktop/deepseek_capture && python3 deepseek_capture.py "你的问题"

# 专家模式
cd ~/Desktop/deepseek_capture && python3 deepseek_capture.py "专家" "你的问题"

# URL 抓取
cd ~/Desktop/deepseek_capture && python3 deepseek_capture.py "你的问题" --frida
```

## 五、下一步

1. **Summary 提取**: 点击引用打开 WebView 后抓内容
2. **URL 捕获率提升**: 目前 100%，长期验证稳定性
3. **智能搜索 toggle 自动化**: 确保每次快速模式开启搜索
