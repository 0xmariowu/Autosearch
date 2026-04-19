# 工具类 · 免 key 免 cookie 调研
> 时间：2026-04-19

## TL;DR
- 验证通过：20 | 失败：6 | 未测：0
- 建议接入 AutoSearch 前 3 个：Nominatim OSM、Open-Meteo、Nager.Date Public Holidays

## ✅ 验证通过
### Free Dictionary API
- URL：`https://api.dictionaryapi.dev/api/v2/entries/en/{word}`
- 认证：none
- 返回：`JSON`
- 样本：`noun: A collection of sheets of paper bound together to hinge at one edge, containing printed or written material, …`；`noun: A long work fit for publication, typically prose, such as a novel or textbook, and typically published as suc…`；`noun: A major division of a long work.`
- 响应时间：`61 ms`
- 接入代码：`httpx.get("https://api.dictionaryapi.dev/api/v2/entries/en/book", timeout=15.0)`

### MyMemory Translation
- URL：`https://api.mymemory.translated.net/get?q={text}&langpair=en|es`
- 认证：none
- 返回：`JSON`
- 样本：`hello world -> Hola Mundo`；`weather forecast -> predicción del tiempo`；`dictionary -> diccionario`
- 响应时间：`1138 ms`
- 接入代码：`httpx.get("https://api.mymemory.translated.net/get", params={"q":"hello world","langpair":"en|es"}, timeout=15.0)`

### Open-Meteo
- URL：`https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m&forecast_days=1&timezone=Asia/Singapore`
- 认证：none
- 返回：`JSON`
- 样本：`2026-04-19T00:00 temp=27.5C`；`2026-04-19T01:00 temp=27.3C`；`2026-04-19T02:00 temp=26.9C`
- 响应时间：`1890 ms`
- 接入代码：`httpx.get("https://api.open-meteo.com/v1/forecast", params={"latitude":1.2897,"longitude":103.85,"hourly":"temperature_2m","forecast_days":1,"timezone":"Asia/Singapore"}, timeout=15.0)`

### USGS Earthquake
- URL：`https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&orderby=time&limit=3&minmagnitude=4.5`
- 认证：none
- 返回：`GeoJSON`
- 样本：`mag 5.7 | 45 km W of Gunungsitoli, Indonesia`；`mag 4.8 | 126 km N of Lae, Papua New Guinea`；`mag 5.4 | south of the Kermadec Islands`
- 响应时间：`1210 ms`
- 接入代码：`httpx.get("https://earthquake.usgs.gov/fdsnws/event/1/query", params={"format":"geojson","orderby":"time","limit":3,"minmagnitude":4.5}, timeout=15.0)`

### Launch Library 2
- URL：`https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=3`
- 认证：none
- 返回：`JSON`
- 样本：`2026-04-19T10:45:00Z | New Glenn | Blue Origin`；`2026-04-19T14:34:20Z | Falcon 9 Block 5 | SpaceX`；`2026-04-20T06:57:00Z | Falcon 9 Block 5 | SpaceX`
- 响应时间：`657 ms`
- 接入代码：`httpx.get("https://ll.thespacedevs.com/2.2.0/launch/upcoming/", params={"limit":3}, timeout=15.0)`

### Open Food Facts
- URL：`https://world.openfoodfacts.org/api/v2/product/{barcode}.json?fields=code,product_name,brands`
- 认证：none
- 返回：`JSON`
- 样本：`3017620422003 | Nutella | Nutella`；`5449000000996 | Original Taste | Coca-Cola`；`7622210449283 | Prince Goût Chocolat au blé complet | LU, Mondelez`
- 响应时间：`509 ms`
- 备注：`/api/v2/product/{barcode}.json` 可用；本轮 `/api/v2/search` 与 `cgi/search.pl` 都返回 `503`。
- 接入代码：`httpx.get("https://world.openfoodfacts.org/api/v2/product/3017620422003.json", params={"fields":"code,product_name,brands"}, timeout=15.0)`

### PokéAPI
- URL：`https://pokeapi.co/api/v2/pokemon?limit=3`
- 认证：none
- 返回：`JSON`
- 样本：`bulbasaur | https://pokeapi.co/api/v2/pokemon/1/`；`ivysaur | https://pokeapi.co/api/v2/pokemon/2/`；`venusaur | https://pokeapi.co/api/v2/pokemon/3/`
- 响应时间：`63 ms`
- 接入代码：`httpx.get("https://pokeapi.co/api/v2/pokemon", params={"limit":3}, timeout=15.0)`

### Cat Facts
- URL：`https://catfact.ninja/facts?limit=3`
- 认证：none
- 返回：`JSON`
- 样本：`Unlike dogs, cats do not have a sweet tooth. Scientists believe this is due to a mutation in a key …`；`When a cat chases its prey, it keeps its head level. Dogs and humans bob their heads up and down.`；`The technical term for a cat’s hairball is a “bezoar.”`
- 响应时间：`509 ms`
- 接入代码：`httpx.get("https://catfact.ninja/facts", params={"limit":3}, timeout=15.0)`

### Dog Facts
- URL：`https://dogapi.dog/api/v2/facts?limit=3`
- 认证：none
- 返回：`JSON:API`
- 样本：`Dogs can get jealous when their humans display affection toward someone or something else.`；`The world’s smartest dogs are thought to be (1) the Border Collie, (2) the Poodle, and (3) the Gold…`；`The most popular breed of dog in the US is the Labrador Retriever.`
- 响应时间：`1617 ms`
- 接入代码：`httpx.get("https://dogapi.dog/api/v2/facts", params={"limit":3}, timeout=15.0)`

### Wikidata SPARQL
- URL：`https://query.wikidata.org/sparql?query={SPARQL}&format=json`
- 认证：none
- 返回：`SPARQL JSON`
- 样本：`Singapore`；`Marsiling`；`Singapore`
- 响应时间：`1225 ms`
- 接入代码：`httpx.get("https://query.wikidata.org/sparql", params={"query": sparql, "format":"json"}, timeout=15.0)`

### Wikipedia API
- URL：`https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json&srlimit=3`
- 认证：none
- 返回：`JSON`
- 样本：`Meteor | A <span class="searchmatch">meteor</span>, known colloquially as a sh…`；`Gloster Meteor | The Gloster <span class="searchmatch">Meteor</span> was the first Bri…`；`Meteor (missile) | The <span class="searchmatch">Meteor</span> is a European active rada…`
- 响应时间：`347 ms`
- 接入代码：`httpx.get("https://en.wikipedia.org/w/api.php", params={"action":"query","list":"search","srsearch":"meteor","format":"json","srlimit":3}, timeout=15.0)`

### Nominatim OSM
- URL：`https://nominatim.openstreetmap.org/search?q={query}&format=jsonv2&limit=3`
- 认证：none（建议显式带 `User-Agent`）
- 返回：`JSON`
- 样本：`Springfield, Sangamon County, Illinois, United States | lat=39.7990175 lon=-89.6439575`；`Springfield, Hampden County, Massachusetts, United States | lat=42.1018764 lon=-72.5886727`；`Springfield, Greene County, Missouri, United States | lat=37.2081729 lon=-93.2922715`
- 响应时间：`968 ms`
- 接入代码：`httpx.get("https://nominatim.openstreetmap.org/search", params={"q":"Springfield","format":"jsonv2","limit":3}, headers={"User-Agent":"AutoSearch/1.0"}, timeout=15.0)`

### ip-api.com
- URL：`http://ip-api.com/json/{ip}?fields=status,country,regionName,city,lat,lon,query`
- 认证：none（免费层仅 HTTP）
- 返回：`JSON over HTTP`
- 样本：`8.8.8.8 | Ashburn, United States | 39.03,-77.5`；`1.1.1.1 | South Brisbane, Australia | -27.4766,153.0166`；`208.67.222.222 | San Jose, United States | 37.4084,-121.954`
- 响应时间：`14 ms`
- 接入代码：`httpx.get("http://ip-api.com/json/8.8.8.8", params={"fields":"status,country,regionName,city,lat,lon,query"}, timeout=15.0)`

### ipwho.is
- URL：`https://ipwho.is/{ip}`
- 认证：none
- 返回：`JSON`
- 样本：`8.8.8.8 | Mountain View, United States | 37.3860517,-122.0838511`；`1.1.1.1 | South Brisbane, Australia | -27.47665,153.01667`；`208.67.222.222 | San Jose, United States | 37.3382082,-121.8863286`
- 响应时间：`63 ms`
- 接入代码：`httpx.get("https://ipwho.is/8.8.8.8", timeout=15.0)`

### QR Code Generator
- URL：`https://api.qrserver.com/v1/create-qr-code/?size=120x120&data={text}`
- 认证：none
- 返回：`PNG image`
- 样本：`AutoSearch | image/png | 309 bytes`；`utility-hunt | image/png | 309 bytes`；`2026-04-19 | image/png | 305 bytes`
- 响应时间：`606 ms`
- 接入代码：`httpx.get("https://api.qrserver.com/v1/create-qr-code/", params={"size":"120x120","data":"AutoSearch"}, timeout=15.0)`

### Nager.Date Public Holidays
- URL：`https://date.nager.at/api/v3/PublicHolidays/{year}/{countryCode}`
- 认证：none
- 返回：`JSON`
- 样本：`2026-01-01 | New Year's Day | New Year's Day`；`2026-01-19 | Martin Luther King, Jr. Day | Martin Luther King, Jr. Day`；`2026-02-12 | Lincoln's Birthday | Lincoln's Birthday`
- 响应时间：`54 ms`
- 接入代码：`httpx.get("https://date.nager.at/api/v3/PublicHolidays/2026/US", timeout=15.0)`

### TimeAPI.io
- URL：`https://timeapi.io/api/Time/current/zone?timeZone={Area}/{City}`
- 认证：none
- 返回：`JSON`
- 样本：`Asia/Singapore | 10:37 | Sunday`；`Europe/London | 03:37 | Sunday`；`America/New_York | 22:37 | Saturday`
- 响应时间：`548 ms`
- 接入代码：`httpx.get("https://timeapi.io/api/Time/current/zone", params={"timeZone":"Asia/Singapore"}, timeout=15.0)`

### Open Library
- URL：`https://openlibrary.org/search.json?q={query}&limit=3`
- 认证：none
- 返回：`JSON`
- 样本：`The Two Towers | 1954 | J.R.R. Tolkien`；`The Fellowship of the Ring | 1954 | J.R.R. Tolkien`；`The Return of the King | 1950 | J.R.R. Tolkien`
- 响应时间：`906 ms`
- 接入代码：`httpx.get("https://openlibrary.org/search.json", params={"q":"tolkien","limit":3}, timeout=15.0)`

### JokeAPI
- URL：`https://v2.jokeapi.dev/joke/Any?amount=3&type=single`
- 认证：none
- 返回：`JSON`
- 样本：`My wife is really mad at the fact that I have no sense of direction. So I packed up my stuff and ri…`；`To whoever stole my copy of Microsoft Office, I will find you. You have my Word!`；`My girlfriend's dog died, so I tried to cheer her up by getting her an identical one. It just made …`
- 响应时间：`245 ms`
- 接入代码：`httpx.get("https://v2.jokeapi.dev/joke/Any", params={"amount":3,"type":"single"}, timeout=15.0)`

### Zen Quotes
- URL：`https://zenquotes.io/api/quotes`
- 认证：none
- 返回：`JSON`
- 样本：`Your success and happiness lie in you. | Helen Keller`；`One must be deeply aware of the impermanence of the world. | Dogen`；`Don't be afraid that you do not know something. Be afraid of not learning about… | Zen Proverb`
- 响应时间：`1570 ms`
- 接入代码：`httpx.get("https://zenquotes.io/api/quotes", timeout=15.0)`

## ❌ 失败
- `LibreTranslate public instance`：`https://libretranslate.de/translate`；POST 返回 `200 text/html` 首页，不是 JSON 翻译结果
- `NASA APOD via DEMO_KEY`：`https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY&count=3`；本轮返回 `503 upstream connect error`；且 `DEMO_KEY` 不满足“免 key”硬标准
- `Numbers API`：`http://numbersapi.com/42?json`；本轮 `15s` 内 `ConnectTimeout`，且免费端仅 HTTP
- `World Time API`：`https://worldtimeapi.org/api/timezone/Asia/Singapore`；连续返回 `connection reset by peer`
- `Quotable`：`https://api.quotable.io/quotes?limit=3`；DNS 解析失败：`nodename nor servname provided`
- `TheColorAPI`：`https://www.thecolorapi.com/scheme?hex=0047AB&mode=analogic&count=3`；返回 `503 Application Error`（Heroku error page）

## ⚠️ 未测
- 无
