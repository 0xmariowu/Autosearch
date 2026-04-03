### ddgs (meta-search) — 24 skills
- **Platform**: load_ddgs_proxy, select_engines, fetch_http_content, normalize_result_fields, aggregate_results, rank_results, resolve_proxy_config
- **Search**: search_text, query_wikipedia, query_grokipedia, bootstrap_vqd_token, search_images, search_videos, search_news, normalize_news_dates, search_books
- **Extraction**: extract_content
- **Serving**: render_cli_results, persist_cli_results, download_result_assets, serve_rest_search, serve_rest_extract, expose_mcp_tools, mount_mcp_sse
- Unique: provider-aware aggregation, normalization in __setattr__, vqd bootstrap pattern
