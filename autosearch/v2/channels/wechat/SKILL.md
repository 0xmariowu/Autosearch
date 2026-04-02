---
name: wechat
description: "Use this channel for WeChat article discovery through Sogou when Chinese news, essays, or公众号 posts are likely to contain the strongest evidence."
categories: [news, social]
platform: weixin.sogou.com
api_key_required: false
aliases: []
---

## When to use

Use when the query is Chinese-language and the likely evidence lives in WeChat public account articles, opinion pieces, or reposted news content.

## Quality signals

- Strong title overlap with the query
- Clear snippet text from the article preview
- Publish timestamps and recognizable publication sources

## Known limits

- Access depends on Sogou's WeChat portal rather than an official API
- Redirect links often need a follow-up fetch to reach the final article
- Result quality varies with Sogou indexing and censorship behavior
