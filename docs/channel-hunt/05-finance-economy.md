# 金融 + 经济 · 免 key 免 cookie 调研
> 时间：2026-04-19

## TL;DR
- 验证通过：10 | 失败：7 | 未测：1
- 建议接入前 3 个：World Bank Open Data、Frankfurter、SEC EDGAR submissions
- `public-apis` README 里真正值得接的匿名源，集中在 `Finance / Currency Exchange / Cryptocurrency` 三段：`World Bank`、`SEC EDGAR Data`、`Frankfurter`、`CoinGecko`、`CoinLore`、`CoinPaprika`、`Binance`（仅 market data）、`U.S. Treasury Fiscal Data`
- `mcpmarket` 搜到的 `Mcprice / FinanceQuote / Finance MCP / Crypto MCP` 主要是对 `Yahoo Finance / Binance / CoinGecko / CoinGlass` 的包装，不是新的原始免鉴权源

## ✅ 验证通过
### Yahoo Finance unofficial
- URL 模板：`https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d`
- 认证：none；本机未装 `yfinance`，但其底层 `query1` 端点匿名可达
- 返回格式：JSON
- 样本 3 条：`2026-04-15 close=266.43`；`2026-04-16 close=263.40`；`2026-04-17 close=270.23`
- 响应时间：`486 ms`
- 限流提示：未见限流头；非官方接口，建议缓存并保守自限 `<=1 req/s`
- AutoSearch 接入代码：`httpx.get("https://query1.finance.yahoo.com/v8/finance/chart/AAPL", params={"interval":"1d","range":"5d"}, timeout=15.0)`

### CoinGecko
- URL 模板：`https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies={vs}`
- 认证：none
- 返回格式：JSON
- 样本 3 条：`bitcoin=75624 USD`；`ethereum=2346.26 USD`；`solana=85.75 USD`
- 响应时间：`55 ms`
- 限流提示：未见限流头；公共匿名源，建议缓存热门币种
- AutoSearch 接入代码：`httpx.get("https://api.coingecko.com/api/v3/simple/price", params={"ids":"bitcoin,ethereum,solana","vs_currencies":"usd"}, timeout=15.0)`

### Binance public market data
- URL 模板：`https://api.binance.com/api/v3/ticker/price?symbols=["BTCUSDT","ETHUSDT","SOLUSDT"]`
- 认证：none（仅市场数据；交易接口需签名）
- 返回格式：JSON
- 样本 3 条：`BTCUSDT=75609.82000000`；`ETHUSDT=2345.72000000`；`SOLUSDT=85.75000000`
- 响应时间：`226 ms`
- 限流提示：响应头返回 `x-mbx-used-weight: 4`、`x-mbx-used-weight-1m: 4`；按 weight 模型控频
- AutoSearch 接入代码：`httpx.get("https://api.binance.com/api/v3/ticker/price", params={"symbols": '["BTCUSDT","ETHUSDT","SOLUSDT"]'}, timeout=15.0)`

### Frankfurter
- URL 模板：`https://api.frankfurter.app/latest?from={base}&to={symbols}`
- 认证：none
- 返回格式：JSON
- 样本 3 条：`EUR=0.84767`；`JPY=159.13`；`SGD=1.2723`
- 响应时间：`132 ms`
- 限流提示：未见限流头；更适合做缓存型 FX 数据，不要当高频 tick 源
- AutoSearch 接入代码：`httpx.get("https://api.frankfurter.app/latest", params={"from":"USD","to":"EUR,JPY,SGD"}, timeout=15.0)`

### open.er-api.com
- URL 模板：`https://open.er-api.com/v6/latest/{base}`
- 认证：none
- 返回格式：JSON
- 样本 3 条：`EUR=0.848763`；`JPY=158.669348`；`SGD=1.27005`
- 响应时间：`58 ms`
- 限流提示：未见限流头；更新节奏偏日级，适合汇率快取
- AutoSearch 接入代码：`httpx.get("https://open.er-api.com/v6/latest/USD", timeout=15.0)`

### SEC EDGAR submissions
- URL 模板：`https://data.sec.gov/submissions/CIK##########.json`
- 认证：none；请求时应带 `User-Agent`
- 返回格式：JSON
- 样本 3 条：`2026-04-17 4 0001140361-26-015421`；`2026-04-17 4 0001140361-26-015420`；`2026-04-03 4 0001140361-26-013192`
- 响应时间：`450 ms`
- 限流提示：未见限流头；遵守 SEC fair access，低频抓取 + 明确 `User-Agent`
- AutoSearch 接入代码：`httpx.get("https://data.sec.gov/submissions/CIK0000320193.json", headers={"User-Agent":"AutoSearch/1.0 (research smoke test)"}, timeout=15.0)`
- 备注：`Anthropic` 不是常规公开 SEC filer，不能像 `AAPL` 一样直接命中 `submissions` 路径

### World Bank Open Data
- URL 模板：`https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json`
- 认证：none
- 返回格式：JSON
- 样本 3 条：`2024=28.75T USD`；`2023=27.29T USD`；`2022=25.60T USD`
- 响应时间：`1202 ms`
- 限流提示：未见限流头；建议分页抓取并做本地缓存
- AutoSearch 接入代码：`httpx.get("https://api.worldbank.org/v2/country/US/indicator/NY.GDP.MKTP.CD", params={"format":"json"}, timeout=15.0)`

### CoinLore
- URL 模板：`https://api.coinlore.net/api/tickers/?start={offset}&limit={n}`
- 认证：none
- 返回格式：JSON
- 样本 3 条：`BTC=75601.80 USD`；`ETH=2346.08 USD`；`USDT=1.00 USD`
- 响应时间：`251 ms`
- 限流提示：未见限流头；建议自限并缓存榜单页
- AutoSearch 接入代码：`httpx.get("https://api.coinlore.net/api/tickers/", params={"start":0,"limit":3}, timeout=15.0)`

### U.S. Treasury Fiscal Data
- URL 模板：`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/rates_of_exchange?...`
- 认证：none
- 返回格式：JSON
- 样本 3 条：`2026-03-31 Afghanistan-Afghani=64.77`；`2026-03-31 Albania-Lek=83.3`；`2026-03-31 Algeria-Dinar=132.596`
- 响应时间：`1457 ms`
- 限流提示：未见限流头；适合分页拉取，不适合高频轮询
- AutoSearch 接入代码：`httpx.get("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/rates_of_exchange", params={"fields":"record_date,country_currency_desc,exchange_rate","sort":"-record_date","page[size]":3}, timeout=15.0)`

### CoinPaprika
- URL 模板：`https://api.coinpaprika.com/v1/tickers?limit={n}`
- 认证：none
- 返回格式：JSON
- 样本 3 条：`BTC=75640.81 USD`；`ETH=2347.15 USD`；`USDT=1.0 USD`
- 响应时间：`69 ms`
- 限流提示：未见限流头；建议自限并做缓存
- AutoSearch 接入代码：`httpx.get("https://api.coinpaprika.com/v1/tickers", params={"limit":3}, timeout=15.0)`

## ❌ 验证失败
- ExchangeRate.host：`https://api.exchangerate.host/live?source=USD&currencies=EUR,JPY,SGD` 匿名请求返回 `missing_access_key`
- CoinCap：`https://api.coincap.io/v2/assets?ids=bitcoin,ethereum,solana` 在本轮环境 DNS 失败；当前官方文档也已改成 `Authorization: Bearer`
- Nasdaq Data Link：`https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json` 匿名请求 `403`
- Alpha Vantage：`https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL` 返回 `apikey is invalid or missing`
- CoinGlass：`https://open-api-v4.coinglass.com/api/futures/supported-coins` 返回 `{"code":"401","msg":"API key missing."}`
- Dune Analytics：`https://api.dune.com/api/v1/query/123/results` 返回 `401 invalid API Key`
- FRED：`https://api.stlouisfed.org/fred/series?series_id=GDP&file_type=json` 匿名请求在 `15s` 内超时；官方文档本身也要求 `api_key`

## ⚠️ 未测
- IMF SDMX API：`https://sdmxcentral.imf.org/ws/public/sdmxapi/rest/dataflow/all/all/latest` 可匿名 `200` 返回 XML，至少能枚举 `BPM6_BOP_M / BPM6_BOP_Q / BPM6_FDI_A` 等 dataflow；但本轮未补到稳定的经济指标 `data` query 模板，先不列入 PASS
