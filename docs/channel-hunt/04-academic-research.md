# 学术 / 研究数据源 · 免 key 免 cookie 调研

> 时间：2026-04-19
> 调研员：Codex (auto)
> 范围：补充 `Paper Search MCP` 已覆盖的 `arXiv / PubMed / Semantic Scholar / OpenAlex`

## TL;DR
- 验证通过：5 个
- 验证失败：5 个
- 未测 / 待补：8 个
- 建议优先接入 AutoSearch 前 5 个：DBLP、Europe PMC、Crossref、INSPIRE HEP、Open Library（Books layer）
- `public-apis` 本轮从 `Science` 区真正值得看的学术候选主要是 `inspirehep.net`、`NASA ADS`、`CORE`；其中 `NASA ADS` 明确要 token，`CORE` 的 `public-apis` 标注与官网现状有出入，需保守处理
- `mcpmarket` 本轮搜到的主要是包装层，不是新的原始数据源：`Academic Search` 主要接 `Semantic Scholar + Crossref`，`Research Automation` 主要接 `arXiv + Crossref`，`Scholarly Research` 主要接 `PubMed + Google Scholar + ArXiv + JSTOR`
- 本地 shell 外网 DNS 受限；`/tmp/channel-hunt/academic/` 已创建。匿名可用性以 Web 侧抓取和官方文档复核为准，因此响应时间统一记为 `N/A`

## ✅ 验证通过

### DBLP
- **URL 模板**: `https://dblp.org/search/publ/api?q=transformer&h=3&format=json`
- **认证**: none
- **返回格式**: JSON / XML / JSONP
- **响应时间**: `N/A`
- **样本**（query=`transformer`）:
  - Transformer-Squared: Self-adaptive LLMs. · DOI `10.48550/ARXIV.2501.06252` · 2025
  - Faster Convergence for Transformer Fine-tuning with Line Search Methods. · DOI `10.48550/ARXIV.2403.18506` · 2024
  - Real-Time Image Segmentation via Hybrid Convolutional-Transformer Architecture Search. · DOI `10.48550/ARXIV.2403.10413` · 2024
- **依据**: 官方 FAQ 明确给出 `/search/publ/api`、`format=json`、`h`/`f` 分页参数，并说明数据为开放元数据
- **文档**: https://dblp.org/faq/How%2Bto%2Buse%2Bthe%2Bdblp%2Bsearch%2BAPI.html
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get(
      "https://dblp.org/search/publ/api",
      params={"q": "transformer", "h": 3, "format": "json"},
      timeout=15.0,
  )
  ```

### Europe PMC
- **URL 模板**: `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=transformer&pageSize=3&format=json`
- **认证**: none
- **返回格式**: JSON / XML / Dublin Core
- **响应时间**: `N/A`
- **字段**（官方 docs）:
  - `search` 模块接受自由文本 query
  - `resultType=lite|core`，其中 `core` 返回更完整元数据
  - JSON 响应里有 `resultList.result[]`，可取 `title`、`doi`、`pubYear`、`citedByCount`、`abstractText`
- **依据**: 官方 RESTful Web Service 文档明确公开 `GET /search`，并给出 `format=json` 与 `query=` 用法
- **文档**: https://europepmc.org/RestfulWebService
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get(
      "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
      params={"query": "transformer", "pageSize": 3, "format": "json"},
      timeout=15.0,
  )
  ```

### Crossref
- **URL 模板**: `https://api.crossref.org/works?query.title=<paper-title>&select=DOI,title,author,published&rows=3`
- **认证**: none
- **返回格式**: JSON
- **响应时间**: `N/A`
- **样本**（specific DOI / paper title）:
  - DOI 直取：`https://api.crossref.org/works/10.1128/mbio.01735-25`
  - 标题检索：`Temporal variability in nutrient transport in a first-order agricultural basin in southern Ontario`
  - 书目信息检索：`The generic name Mediocris (Cetacea: Delphinoidea: Kentriodontidae), belongs to a foraminiferan 2006`
- **依据**: 官方文档明确写明 REST API 可公开匿名访问；社区支持贴也给出 `query.title` / `query.bibliographic` / `select=DOI` 的真实查询范式
- **文档**:
  - https://www.crossref.org/documentation/retrieve-metadata/rest-api/
  - https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get(
      "https://api.crossref.org/works",
      params={
          "query.title": "Attention Is All You Need",
          "select": "DOI,title,author,published",
          "rows": 3,
      },
      timeout=15.0,
  )
  ```

### INSPIRE HEP
- **URL 模板**: `https://inspirehep.net/api/literature?q=transformer&size=3`
- **认证**: none
- **返回格式**: JSON
- **响应时间**: `N/A`
- **样本**（query=`transformer` / HEP 相关）:
  - Measurements With A Quantum Vision Transformer: A Naive Approach · 2024
  - Experimental Investigation of High Transformer Ratio Plasma Wakefield Acceleration at PITZ · proceedings record
  - Attention for SWGO Reconstruction · 2025
- **依据**: INSPIRE FAQ 明确写明“有 REST API allowing scripts”；官方博客明确说明新 API 以 JSON 为主格式、可程序化访问 search 和 detailed record pages
- **说明**: `literature` 路径是基于 INSPIRE 公开 REST API 命名与当前 collection 命名推断，适合作为接入候选；若落地实现，建议再补一次真实 200 烟测
- **文档**:
  - https://help.inspirehep.net/knowledge-base/faq/
  - https://blog.inspirehep.net/2020/06/we-released-the-new-inspire-api/
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get(
      "https://inspirehep.net/api/literature",
      params={"q": "transformer", "size": 3},
      timeout=15.0,
  )
  ```

### Open Library
- **URL 模板**: `https://openlibrary.org/search.json?q=transformer&limit=3`
- **认证**: none
- **返回格式**: JSON
- **响应时间**: `N/A`
- **样本**（specific title / docs examples）:
  - `https://openlibrary.org/search.json?q=the+lord+of+the+rings`
  - `https://openlibrary.org/search.json?title=the+lord+of+the+rings`
  - `https://openlibrary.org/search.json?q=crime+and+punishment&fields=key,title,author_name,editions`
- **依据**: 官方 Search API 文档给出 `search.json`、参数说明与响应 JSON 结构；适合补足 books / monographs 层，不适合替代论文源
- **文档**:
  - https://openlibrary.org/dev/docs/api/search
  - https://openlibrary.org/developers/api
- **AutoSearch 接入代码**:
  ```python
  resp = httpx.get(
      "https://openlibrary.org/search.json",
      params={"q": "transformer", "limit": 3},
      timeout=15.0,
  )
  ```

## ❌ 验证失败
- NASA ADS: 官方帮助页明确要求先获取 API token；`public-apis` 里也把它标成 `OAuth`，不满足“免 key / 免 token”标准。文档：https://ui.adsabs.harvard.edu/help/api/
- OpenReview: 当前 OpenAPI 文档把 `/notes/search` 标成需要 `cookieAuth` / `openreview.accessToken`；不算匿名开放搜索。文档：https://docs.openreview.net/reference/api-v2/openapi-definition
- ORCID API: 搜索教程明确写明 search 需要 `/read-public` access token；虽然 ORCID 有 anonymous/public API 概念，但“搜索注册表”这条不满足本轮无 auth 标准。文档：https://info.orcid.org/documentation/api-tutorials/api-tutorial-searching-the-orcid-registry/
- Zenodo REST API: 官方开发者文档在认证章节写的是 “All API requests must be authenticated”；`Records` 虽然是搜索 published records，但当前公开文档仍以 Bearer token 为准。文档：https://developers.zenodo.org/
- ACL Anthology: 官方 FAQ 说程序化访问主要走 GitHub repo 元数据和 `acl-anthology` Python 模块，而不是一个现成的匿名 HTTP search API；不符合本轮 PASS 定义。文档：https://aclanthology.org/faq/api/

## ⚠️ 未测（建议跟进）
- CORE: 官网现在写了“free API access without registration, subject to our rate limits”，但文档页与 landing page 仍强烈引导注册 API key；而且本轮没补到一个无歧义、可直接抄走的匿名 query URL 模板，先放灰名单。文档：
  - https://core.ac.uk/services/api
  - https://core.ac.uk/documentation/api
- Connected Papers: 本轮未找到官方公开 API 文档；产品价值高，但当前更像 Web UI / graph 服务，需单独补查匿名接口
- arXiv-sanity-lite: 站点可用性看起来更像公开前端，不是正式 API；建议单测是否存在稳定 JSON search endpoint
- Lens.org: 有 free tier 价值，但本轮未补到“匿名无 auth”证据；大概率需要账号或 token，需单独核查
- Papers with Code: 站点和 paper/method 页面公开可读，但本轮没补到稳定、官方文档化的匿名 API 查询路径；建议单独测 `api/v1` 是否仍可匿名使用
- Hugging Face Papers: 页面公开，但本轮未确认有稳定、文档化的匿名 papers API；建议单测站点内部 JSON 接口是否可长期依赖
- FatCat / Internet Archive Scholar: 本轮没补到稳定官方 API 文档与匿名 query 样本；值得再查，因为它可能补到 archive / citation / preservation 维度
- Google Scholar via `scholarly`: 仍然有研究价值，但从稳定性和反爬角度看很脆；适合保留为脆弱后备源，不适合主链路
