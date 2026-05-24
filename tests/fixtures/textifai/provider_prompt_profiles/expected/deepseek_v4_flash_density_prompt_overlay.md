Provider-specific extraction density instructions for DeepSeek V4 Flash:

- Do not compress the extraction into only the main summary.
- Return all schema sections, even when some are short.
- Do not omit structurally relevant objects, tools, catalysts, weapons, artifacts, keys, or persistent props.
- Do not omit durable events that change state, identity, location, threat, relationship, or magic/system status.
- Do not omit key relations when evidence supports them.
- Keep facts concise, but preserve coverage.
- Use unresolved_mentions for important unresolved references instead of dropping them.
- Keep uncertain identities in review; do not auto-promote.
- Return one valid JSON object only.
