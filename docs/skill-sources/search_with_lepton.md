### search_with_lepton (ai-search) — 36 skills
- **Search Backend Adapters**: select_search_backend, search_bing, search_google_cse, search_serper, normalize_serper_results, search_searchapi, normalize_searchapi_results, search_lepton_remote
- **RAG Orchestration**: create_threadlocal_llm_client, login_lepton_workspace, sanitize_query, apply_default_query, format_citation_context, generate_answer_stream, generate_related_questions
- **Streaming, Cache & API**: expose_query_endpoint, initialize_kv_workspace, replay_cached_result, emit_context_stream, emit_answer_stream, emit_related_question_stream, warn_on_empty_search, asynchronously_cache_stream
- **Frontend Query Flow**: construct_search_url, submit_search_form, read_search_params, rewrite_search_with_new_uuid, fetch_query_stream
- **Frontend Stream Parsing**: pump_response_chunks, parse_stream_sections, normalize_citation_markdown, route_stream_updates
- **Result Rendering**: render_markdown_answer, preview_citation_source, render_source_grid, render_related_queries, display_loading_skeletons, display_error_overlay
- **Hosting & Deployment**: mount_static_ui, redirect_root_ui, export_static_nextjs_ui
- Unique: The project’s most distinctive pattern is its lightweight multiplexed stream protocol: raw sources first, then answer text, then related questions, separated by explicit markers the UI incrementally parses. It also couples that stream with KV-backed replay keyed by `search_uuid`, making generated results both shareable and cacheable without rerunning search plus generation.