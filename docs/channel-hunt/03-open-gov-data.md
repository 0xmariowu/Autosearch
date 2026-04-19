# 开放政府 / 开放数据 · 免 key 免 cookie 调研

> 时间：2026-04-19
> 调研员：Codex (auto)

## TL;DR
- 验证通过：7 个
- 验证失败：1 个
- 未测：8 个
- 建议优先接入 AutoSearch 前 5 个：Census.gov、data.gov.sg、Data.gov Catalog、World Bank Open Data、data.gov.uk
- `public-apis` 的 `Government` 区仍然能挖到一批免 key 目标：`Census.gov`、`EPA`、`Federal Register`、`USAspending.gov`、`Open Government, UK/Australia/Singapore`；但条目质量不一致，`Data.gov` 仍被旧 README 标成 `apiKey`，而当前官方 Catalog API 文档已明确写成“no API key required”
- `mcpmarket` 本轮搜到的主要是 MCP 包装层，不是新的原始数据源：`Open Data`、`Data.gov`、`Opengov`、`World Bank`、`SCB Open Data`
- 本地 shell 外网 DNS 受限；`/tmp/channel-hunt/open-gov/` 已补 `curl` / `httpx` 烟测模板与限制说明，内容有效性以浏览器侧抓取和官方文档复核为准

## ✅ 验证通过

### Census.gov
- **URL 模板**: `https://api.census.gov/data/2020/dec/pl?get=NAME&for=state:*`
- **认证**: none（官方示例常带 `key=`，但匿名浏览器请求直接返回 `200` JSON）
- **返回格式**: JSON
- **样本**（匿名 query 返回前 3 行）:
  - Pennsylvania · `42`
  - California · `06`
  - West Virginia · `54`
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get("https://api.census.gov/data/2020/dec/pl", params={"get": "NAME", "for": "state:*"}, timeout=15.0)
  ```

### data.gov.sg
- **URL 模板**: `https://data.gov.sg/api/action/datastore_search?resource_id=d_8b84c4ee58e3cfc0ece0d773c8ca6abc&limit=3`
- **认证**: none for testing（官方文档明确：All Data.gov.sg APIs are public；生产环境建议申请 key 以提高限额）
- **返回格式**: JSON
- **样本**（官方 `datastore_search` 示例响应）:
  - `1960` · `Total Residents` · `1646400`
  - `1960` · `Total Male Residents` · `859600`
  - `1960` · `Total Female Residents` · `786800`
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get(
      "https://data.gov.sg/api/action/datastore_search",
      params={"resource_id": "d_8b84c4ee58e3cfc0ece0d773c8ca6abc", "limit": 3},
      timeout=15.0,
  )
  ```

### Data.gov Catalog
- **URL 模板**: `https://catalog.data.gov/dataset?q=climate`
- **认证**: none（当前官方 Catalog API 文档写明 “No API key is required. All endpoints are publicly accessible.”）
- **返回格式**: HTML 搜索页 / JSON Catalog API
- **样本**（query=`climate`）:
  - Supply Chain Greenhouse Gas Emission Factors v1.3 by NAICS-6
  - Collection Civil Rights Data Collection (CRDC)
  - Fruit and Vegetable Prices
- **说明**: 浏览器侧已验证公开搜索结果；若后续接 JSON Catalog API，要以当前 `resources.data.gov` 文档为准，不要照抄 `public-apis` 旧条目里的 `apiKey` 标记
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get("https://catalog.data.gov/dataset", params={"q": "climate"}, timeout=15.0)
  ```

### World Bank Open Data
- **URL 模板**: `https://api.worldbank.org/v2/country/US/indicator/NY.GDP.MKTP.CD?format=json`
- **认证**: none（官方文档明确 API keys and other authentication methods are no longer necessary）
- **返回格式**: JSON / XML
- **样本**（美国国家页，浏览器侧复核）:
  - GDP (current US$) · `29.18` trillion · `2024`
  - GDP per capita (current US$) · `85,809.9` · `2024`
  - GDP growth (annual %) · `2.8` · `2024`
- **说明**: 本轮 shell 里没法直连 `api.worldbank.org`，所以样本值取自官方国家页，匿名访问与 API 文档一并复核
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get(
      "https://api.worldbank.org/v2/country/US/indicator/NY.GDP.MKTP.CD",
      params={"format": "json"},
      timeout=15.0,
  )
  ```

### data.gov.uk
- **URL 模板**: `https://data.gov.uk/api/action/package_search?q=climate&rows=3`
- **认证**: none（官方 API 文档明确：You do not need an API key to use the API and there are no rate limits）
- **返回格式**: JSON
- **样本**（英国公开目录中的 climate 相关数据页）:
  - Climate change exposure estimates for the UK at 1 km resolution, 1901-2080
  - Climate Just data
  - Average Rainfall and Temperature
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get(
      "https://data.gov.uk/api/action/package_search",
      params={"q": "climate", "rows": 3},
      timeout=15.0,
  )
  ```

### UNData
- **URL 模板**: `http://data.un.org/ws/rest/{artifact}/{artifact_id}/{parameters}`
- **认证**: none（API manual 写明 UNdata API 提供动态程序化访问；Terms of Use 写明数据免费）
- **返回格式**: XML / JSON / CSV（通过 `Accept` 头选择）
- **样本**（UNData 首页公开表）:
  - Population, surface area and density
  - International migrants and refugees
  - GDP and GDP per capita
- **说明**: 这项 PASS 主要基于官方 API manual + 首页公开数据表复核；本轮未在 shell 里跑通 REST 示例
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get(
      "http://data.un.org/ws/rest/dataflow",
      headers={"Accept": "text/json"},
      timeout=15.0,
  )
  ```

### data.gov.au
- **URL 模板**: `https://data.gov.au/data/dataset/water-data-online`
- **认证**: none
- **返回格式**: HTML 数据集页
- **样本**（公开数据集页）:
  - Water Data Online
  - Real Time Water
  - Water Quality
- **说明**: 本轮更像“开放数据目录 PASS”，不是稳定的统一 JSON API PASS；对 AutoSearch 来说可先接公开 dataset page / file links
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get("https://data.gov.au/data/dataset/water-data-online", timeout=15.0)
  ```

## ❌ 验证失败
- FRED: 官方 2026 文档明确 “All web service requests require an API key”，而且 v2 用 `Authorization: Bearer ...`；不满足本轮“免 key / 无 Authorization”标准

## ⚠️ 未测
- data.sec.gov: 官方 EDGAR API 文档明确写了“不需要 authentication or API keys”，但本轮没在浏览器侧补到一个可直接抄走的匿名 `submissions/CIK##########.json` 真实样本；另外用户举的 “Anthropic” 不适合作为测试对象，因为它不是常规公开 SEC filer
- USGS Earthquake API: 官方 feed 文档和 `4.5_week.geojson` 已能打开 JSON，但本轮没把最近 7 天的 3 条事件样本从浏览器侧完整抽出；应优先补这一项，价值很高
- data.europa.eu: 官方 FAQ 已确认有 Search API / SPARQL / Registry API；但本轮只复核到公开数据门户和单条 dataset 搜索结果，没补齐 3 条可复用样本
- OECD: 需要单独补官方 API 文档与匿名样本；本轮搜索预算耗尽前没拿到足够证据
- IMF: `data.imf.org` 官方页已确认有 SDMX 2.1 / 3.0 API；但当前文档入口混合了 “swagger 需登录 beta portal” 的表述，本轮不把它算稳定 PASS
- NASA APIs: 用户给的 `DEMO_KEY` 路线大概率可用，但本轮没补官方文档页和匿名/APOD 实例响应，不写进 PASS
- OpenAlex: 官方文档在 **2026-02-13** 起切到“API key required”；虽然仍保留少量无 key 测试额度（100 credits/day），但匿名可用性和长期可接入性都在收紧，本轮先不算 PASS
- data.gov.cn: 本轮没有拿到稳定公开 API 文档或匿名可复用样本；建议中文网络环境下单独补测
