---
name: m2_search_query
phase: M2
description: Generate N diverse search queries from a user task, context, and knowledge recall.
---
Write {n} search queries to search online that form an objective view of the following task:
"{task}"

Assume the current date is {today} if required.

Context:
{context}

Use this context to inform and refine your search queries. The context provides task guidance,
evaluation criteria, and known information gaps that should shape more specific and relevant
searches.

Respond in valid JSON with this exact schema:
{{
  "subqueries": [
    {{
      "text": "search query",
      "rationale": "why this query helps cover the task"
    }}
  ]
}}

Rules:
- Return exactly {n} subqueries
- Make the queries mutually complementary rather than redundant
- Prefer concrete search terms over vague natural-language questions
- Use current-year or date terms only when the task is time-sensitive
- Keep each rationale concise and specific
