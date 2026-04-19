# 中文新闻 + 技术媒体 · 免 key 免 cookie 调研

> 时间：2026-04-19
> 调研员：Codex (auto)

## TL;DR
- 验证通过：5 个
- 验证失败：5 个
- 建议接入 AutoSearch 前 3 个：36kr AI 频道、OSChina 资讯页、新浪科技首页
- `public-apis` 与 `mcpmarket` 没挖到可直接替代这些站点的现成免 key 中文媒体 API；本轮可用源仍以公开 HTML 频道页为主
- 本地 shell 外网 DNS 受限，`/tmp/channel-hunt/ch-news/` 已补齐 `httpx` 烟测脚本；内容有效性通过浏览器侧抓取复核

## ✅ 验证通过

### 36kr
- **URL 模板**: `curl -L --max-time 15 -A 'AutoSearch/1.0' 'https://36kr.com/information/AI'`
- **认证**: none
- **返回格式**: HTML
- **样本**（query="AI"）:
  - 对话Edgewell全球AI转型负责人付咏（Sylvia Fu）：以「中国速度」激活全球，用AI重塑消费品巨头的未来 · https://36kr.com/p/3759285853159940 · 2026-04-19
  - 1元买无限Token？小心词元骗局 · https://36kr.com/p/3759334788116997 · 2026-04-09
  - 唯快不破，Anthropic 几天搞定智能体生产 · https://36kr.com/p/3759120023007744 · 2026-04-09
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get("https://36kr.com/information/AI", headers={"User-Agent": "AutoSearch/1.0"}, timeout=15.0)
  ```

### 新浪科技
- **URL 模板**: `curl -L --max-time 15 -A 'AutoSearch/1.0' 'https://tech.sina.com.cn/'`
- **认证**: none
- **返回格式**: HTML
- **样本**（query="AI"）:
  - 对话智元CTO彭志辉：宇树“值得学习”，我们更“全栈”，特斯拉“没法评” · https://finance.sina.com.cn/tech/2026-04-17/doc-inhuutzh3319226.shtml · 2026-04-19
  - 商汤科技拟配售约32亿港元，将推出AI词元计划“Token Plan” · https://finance.sina.com.cn/tech/2026-04-17/doc-inhuuimk6605969.shtml · 2026-04-19
  - OpenAI全面升级Codex对标Claude Code，AI编程工具竞争升温 · https://finance.sina.com.cn/world/2026-04-17/doc-inhutwvs3517643.shtml · 2026-04-19
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get("https://tech.sina.com.cn/", headers={"User-Agent": "AutoSearch/1.0"}, timeout=15.0)
  ```

### OSChina
- **URL 模板**: `curl -L --max-time 15 -A 'AutoSearch/1.0' 'https://www.oschina.net/news/'`
- **认证**: none
- **返回格式**: HTML
- **样本**（query="AI"）:
  - Altman 公布 OpenAI 2025 年将发布的技术产品 · https://www.oschina.net/news/327323 · 2026-04-19
  - 智元机器人重磅开源百万真机数据集 AgiBot World · https://www.oschina.net/news/327297 · 2026-04-19
  - 智谱深度推理模型 GLM-Zero 预览版上线 · https://www.oschina.net/news/327292 · 2026-04-19
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get("https://www.oschina.net/news/", headers={"User-Agent": "AutoSearch/1.0"}, timeout=15.0)
  ```

### V2EX
- **URL 模板**: `curl -L --max-time 15 -A 'AutoSearch/1.0' 'https://www.v2ex.com/?tab=ai'`
- **认证**: none
- **返回格式**: HTML
- **样本**（query="AI"）:
  - 现在还有什么渠道可以稳定安全地使用 Claude 吗？ · https://www.v2ex.com/t/1206406 · 2026-04-19
  - GLM-Coding 调用持续报错：z.ai 的 Lite 套餐几乎无法使用，官方 Pro/Max 是否稳定？ · https://www.v2ex.com/t/1206408 · 2026-04-19
  - claude 认证莫慌 · https://www.v2ex.com/t/1206105 · 2026-04-16
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get("https://www.v2ex.com/?tab=ai", headers={"User-Agent": "AutoSearch/1.0"}, timeout=15.0)
  ```

### InfoQ 中文
- **URL 模板**: `curl -L --max-time 15 -A 'AutoSearch/1.0' 'https://www.infoq.cn/AI'`
- **认证**: none
- **返回格式**: HTML
- **样本**（query="AI"）:
  - 投身蓝海，拥抱生态：百度大牛带你玩转小程序 · https://www.infoq.cn/article/GTfro9SbW5P9Y9oohkP0 · 2026-04-19
  - 闭环管理下的银行监控系统改造 · https://www.infoq.cn/article/XCXwt0yXRJABUFI5rQcb · 2026-04-19
  - 更精准、专业，夸克智能问答系统的构架与实践 · https://www.infoq.cn/article/UWlNts5kYDW8q2GmYU8b · 2025-11-30
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get("https://www.infoq.cn/AI", headers={"User-Agent": "AutoSearch/1.0"}, timeout=15.0)
  ```

## ❌ 验证失败
- 腾讯新闻: `https://news.qq.com/ch/tech/` 当前会话返回 0 行，前端动态渲染，未拿到稳定文章列表
- 网易新闻: `https://tech.163.com/` 直取失败，当前会话无法复现稳定 HTML 列表
- 澎湃新闻: 搜索能看到 AI tag 和相关文章，但直取 tag 页在当前会话 cache miss，不够稳定
- CSDN: `https://bbs.csdn.net/forums/AI` 列表页可开，但详情页多次解析不稳定，未拿到 3 条可复用样本 URL
- 少数派: 首页可开，但本轮未验证到稳定公开 AI 列表/搜索 endpoint，可用样本不足 3 条

## ⚠️ 未测（建议跟进）
- 博客园: `https://www.cnblogs.com/cate/ai/` 分类页很像可用，建议补一次详情页 URL 解析复核
- 虎嗅: 首页与前沿科技区可读，建议补一次文章页日期/URL 齐套校验后再接入
- 财新: 需单独核查是否被付费墙或反爬规则拦截
- 第一财经: 需补稳定的公开频道页或 RSS 入口
- 观察者网: 需补稳定的公开频道页或 RSS 入口
