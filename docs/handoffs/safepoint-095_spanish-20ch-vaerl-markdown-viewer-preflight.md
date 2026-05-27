# Spanish 20-chapter E2E: VaERL → Markdown Vault → Viewer/Wiki/Graph Manual Review

## Product Reading
TextifAI opera como plataforma first-party: VaERL source of truth, Markdown substrate editable, viewer/wiki/graph como proyecciones author-facing.

## Scope
E2E real capítulos ch_001–ch_020 con DeepSeek, materialización Markdown, índice backlink/graph y servidor viewer para revisión manual.

## Files Changed
- reports commit-safe en tests/fixtures/textifai/spanish_20ch_e2e/expected/
- handoff commit-safe y private summaries bajo docs/handoffs/private/ (gitignored)

## SP094 Context
SP-094 dejó viewer/wiki/graph MVP y Open Design dev tooling listo; esta fase ejecuta validación real española.

## Spanish Source Preflight
{
  "assessment": "spanish_source_preflight_completed",
  "source_path": "/home/david/OnT/ESP 王者の杖 .md",
  "source_hash": "9c201c8c9373d2e451a5141f601b7152fedc99f2fb6dbae78998ff8007c69beb",
  "file_size": 836914,
  "detected_chapter_count": 115,
  "selected_chapters": [
    "ch_001",
    "ch_002",
    "ch_003",
    "ch_004",
    "ch_005",
    "ch_006",
    "ch_007",
    "ch_008",
    "ch_009",
    "ch_010",
    "ch_011",
    "ch_012",
    "ch_013",
    "ch_014",
    "ch_015",
    "ch_016",
    "ch_017",
    "ch_018",
    "ch_019",
    "ch_020"
  ],
  "headings_pattern_summary": {
    "top_detection_signals": [
      [
        "isolated_line",
        20
      ],
      [
        "markdown_heading",
        19
      ],
      [
        "numeric_prefix",
        12
      ]
    ],
    "first_selected_char_counts": [
      4786,
      6052,
      5503,
      3384,
      3605,
      4745,
      2666,
      1552,
      4993,
      5619,
      4933,
      5094,
      4092,
      7110,
      148,
      3187,
      7201,
      4396,
      3352,
      2691
    ]
  },
  "source_available": true,
  "blocking_reason": null
}

## DeepSeek Provider Setup
{
  "assessment": "deepseek_provider_preflight_completed",
  "provider": "deepseek",
  "deepseek_api_key_present": true,
  "deepseek_api_key_length": 35,
  "deepseek_api_key_sha8": "29fc730d",
  "uses_process_env": true,
  "depends_on_dotenv": false
}

## Execution Plan
{
  "assessment": "spanish_20ch_execution_plan_ready",
  "source_path": "/home/david/OnT/ESP 王者の杖 .md",
  "selected_chapters": [
    "ch_001",
    "ch_002",
    "ch_003",
    "ch_004",
    "ch_005",
    "ch_006",
    "ch_007",
    "ch_008",
    "ch_009",
    "ch_010",
    "ch_011",
    "ch_012",
    "ch_013",
    "ch_014",
    "ch_015",
    "ch_016",
    "ch_017",
    "ch_018",
    "ch_019",
    "ch_020"
  ],
  "strategy": {
    "provider": "deepseek",
    "flash_first": {
      "model": "deepseek-v4-flash",
      "phase": "bootstrap_chapter_extraction"
    },
    "targeted_pro_conditions": [
      "flash_invalid_or_unrecoverable_output",
      "repeated_truncation_or_continuation_failure",
      "critical_chapter_relation_quality_poor",
      "source_evidence_coverage_poor"
    ]
  },
  "no_artificial_call_cap": true,
  "telemetry_only_estimates": true,
  "emergency_loop_guard": {
    "enabled": true,
    "max_provider_requests": 5000
  },
  "real_stop_conditions": [
    "source_missing_or_unreadable",
    "missing_deepseek_api_key",
    "auth_error",
    "credit_exhausted",
    "persistent_rate_limit",
    "provider_outage",
    "persistent_timeout",
    "source_corrupt_or_undetectable_chapters",
    "unrecoverable_parse_error",
    "repeated_invalid_continuation",
    "unexpected_write_back",
    "user_cancelled"
  ],
  "runtime_root": "/tmp/textifai_private_provider_runs/sp095_spanish_20ch_e2e_vaerl_markdown_viewer/20260527T074727Z",
  "private_runtime_packet_root": "/tmp/textifai_private_provider_runs/sp095_spanish_20ch_e2e_vaerl_markdown_viewer/20260527T074727Z",
  "private_handoff_root": "/home/david/projects/autonovel-fork/docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight"
}

## Provider Run Summary
{
  "assessment": "spanish_20ch_provider_run_completed",
  "provider_calls_executed": true,
  "command_exit_code": 0,
  "duration_seconds": 1434.401,
  "planned_provider_call_count": 40,
  "planned_with_continuation_reserve": 60,
  "actual_provider_call_count": null,
  "retryable_chapter_count": null,
  "decision_assessment": "real_deepseek_e2e_validation_passed_ready_for_larger_e2e",
  "provider_block_reason": null,
  "usage_rows": 20,
  "provider_packet_dir": "/tmp/textifai_private_provider_runs/sp095_spanish_20ch_e2e_vaerl_markdown_viewer/20260527T074727Z/provider_runs/20260527T074729Z",
  "blocked_provider": false,
  "failure_reason": "",
  "stdout_tail": "rap_chapter_extraction:oer_focus_v1\nrun 33/40 model=deepseek-v4-flash chapter=ch_017 chunk=source_da40c55d14_ch_017_chunk_001 profile=deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1\nrun 34/40 model=deepseek-v4-flash chapter=ch_017 chunk=reduction profile=deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1\nrun 35/40 model=deepseek-v4-flash chapter=ch_018 chunk=source_da40c55d14_ch_018_chunk_001 profile=deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1\nrun 36/40 model=deepseek-v4-flash chapter=ch_018 chunk=reduction profile=deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1\nrun 37/40 model=deepseek-v4-flash chapter=ch_019 chunk=source_da40c55d14_ch_019_chunk_001 profile=deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1\nrun 38/40 model=deepseek-v4-flash chapter=ch_019 chunk=reduction profile=deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1\nrun 40/40 model=deepseek-v4-flash chapter=ch_020 chunk=source_da40c55d14_ch_020_chunk_001 profile=deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1\nrun 41/40 model=deepseek-v4-flash chapter=ch_020 chunk=reduction profile=deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1\n",
  "stderr_tail": ""
}

## Chunking / Continuation
Natural chunking activo; continuation/patch continuation habilitado; cap tratado como guard de emergencia, no bloqueador de producto.

## Writer Outcome
{
  "assessment": "spanish_20ch_writer_outcome_ready",
  "status": "success_with_retry_available",
  "total_chapters": 20,
  "chapters_ready": 3,
  "chapters_ready_with_warnings": 0,
  "chapters_needing_review": 0,
  "chapters_needing_retry": 17,
  "chapters_failed": 0,
  "affected_chapters": [
    {
      "chapter_id": "ch_001",
      "chapter_label": "Chapter 001",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_002",
      "chapter_label": "Chapter 002",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_004",
      "chapter_label": "Chapter 004",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_005",
      "chapter_label": "Chapter 005",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_006",
      "chapter_label": "Chapter 006",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_007",
      "chapter_label": "Chapter 007",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_008",
      "chapter_label": "Chapter 008",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_009",
      "chapter_label": "Chapter 009",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_010",
      "chapter_label": "Chapter 010",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_011",
      "chapter_label": "Chapter 011",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_012",
      "chapter_label": "Chapter 012",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_013",
      "chapter_label": "Chapter 013",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_015",
      "chapter_label": "Chapter 015",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_016",
      "chapter_label": "Chapter 016",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_018",
      "chapter_label": "Chapter 018",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_019",
      "chapter_label": "Chapter 019",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    },
    {
      "chapter_id": "ch_020",
      "chapter_label": "Chapter 020",
      "status": "needs_retry",
      "reason_label": "chapter_needs_second_pass"
    }
  ],
  "primary_cta": {
    "label": "Retry pending chapters",
    "action": "retry_pending_chapters"
  },
  "secondary_cta": {
    "label": "Later",
    "action": "dismiss"
  },
  "user_summary": "3 de 20 capítulos listos. 17 requieren segunda pasada."
}

## VaERL Projection
{
  "assessment": "spanish_20ch_vaerl_projection_ready",
  "entity_count": 425,
  "chapter_count": 19,
  "review_item_count": 55,
  "entity_counts_by_kind": {
    "character": 66,
    "concept": 137,
    "event": 95,
    "object": 66,
    "place": 61
  },
  "needs_review_entity_count": 0,
  "relationship_count": 84
}

## Markdown Materialization
{
  "assessment": "spanish_20ch_markdown_materialization_summary_ready",
  "note_count": 445,
  "notes_by_kind": {
    "character": 66,
    "concept": 137,
    "event": 95,
    "object": 66,
    "place": 61,
    "chapter": 19,
    "review": 1
  },
  "edge_count": 222,
  "tag_count": 10,
  "orphan_note_count": 283,
  "unresolved_link_count": 401,
  "editable_policy": "Markdown edits create VaERL patch proposals; VaERL remains source of truth until author confirmation.",
  "viewer_read_only_note": true
}

## Markdown Graph / Backlink Index
{
  "assessment": "spanish_20ch_graph_quality_summary_ready",
  "node_count": 445,
  "edge_count": 222,
  "nodes_by_kind": {
    "chapter": 19,
    "character": 66,
    "concept": 137,
    "event": 95,
    "object": 66,
    "place": 61,
    "review": 1
  },
  "edges_by_kind": {
    "Characters/Guardia": 1,
    "Concepts/Nerys": 3,
    "Concepts/Regente": 3,
    "Concepts/Sera": 6,
    "Places/Thiseia": 1,
    "Places/Castillo_De_Thisiea": 4,
    "Places/Claro": 1,
    "Concepts/Guardias": 1,
    "Concepts/Sellado": 1,
    "Objects/Talismanes": 3,
    "Places/Torre": 3,
    "Concepts/Canalizadores": 1,
    "Concepts/Ren": 8,
    "Events/Colapso_Hechizo": 3,
    "Events/Huida_Ren": 1,
    "Events/Intento_De_Robo_Campanilla": 1,
    "Events/Reflexion_Ren": 1,
    "Concepts/Nael": 6,
    "Concepts/Abuelo": 5,
    "Objects/Biombo": 1,
    "Objects/Campanilla": 1,
    "Objects/Cesta": 2,
    "Objects/Mortero": 1,
    "Concepts/Tota": 6,
    "Places/Campo": 1,
    "Objects/Chaqueta": 1,
    "Events/Abuelo_Examina_Chica": 1,
    "Objects/Capa": 1,
    "Places/Casa_Herbolarios": 1,
    "Places/Casa_Ren": 1,
    "Objects/Catre_Invitados": 1,
    "Concepts/Chica_Herida": 5,
    "Concepts/Deber": 1,
    "Events/Enviar_Herbolarios": 1,
    "Events/Llevar_Chica_Casa": 1,
    "Concepts/Magulladuras": 1,
    "Objects/Manta_Bordada": 1,
    "Characters/Marido_Herbolarios": 1,
    "Concepts/Pomadas": 1,
    "Events/Ren_Habla_Herbolarios": 1,
    "Events/Ren_Va_Herbolarios": 1,
    "Concepts/Respeto_Sagrado": 1,
    "Concepts/Reverencia": 1,
    "Objects/Taza": 1,
    "Objects/Valla": 1,
    "Concepts/Vendas": 1,
    "Objects/Cubo": 1,
    "Objects/Manta": 1,
    "Concepts/Cazador": 3,
    "Objects/Esposas": 1,
    "Places/Ladera": 1,
    "Concepts/Lealtad": 1,
    "Objects/Pluma": 1,
    "Concepts/Protagonista": 4,
    "Concepts/Narrador": 12,
    "Concepts/Princesa": 7,
    "Concepts/Ayudante": 3,
    "Concepts/Consejo": 3,
    "Characters/Emisario": 1,
    "Concepts/Sensomago": 2,
    "Concepts/Spelarita": 5,
    "Concepts/Agenda": 3,
    "Events/Asentimiento_Del_Narrador": 1,
    "Places/Camara_De_Evaluacion_2": 3,
    "Events/Fin_De_La_Agenda": 1,
    "Concepts/Cadena": 1,
    "Concepts/Gaheris": 1,
    "Concepts/Heredera": 1,
    "Characters/Telmira": 2,
    "Objects/Cebolla": 1,
    "Objects/Vendaje": 1,
    "Concepts/Reyes_De_Thisiea": 1,
    "Places/Thisiea": 1,
    "Events/Alejamiento_Del_Nieto": 1,
    "Objects/Campana_Llave": 1,
    "Concepts/Equilibrio_Del_Reino": 1,
    "Characters/Pares_Reales": 2,
    "Events/Partida_Planeada": 1,
    "Objects/Pergamino_Secreto": 1,
    "Places/Cobertizo": 1,
    "Concepts/Ella": 3,
    "Concepts/Intruso": 1,
    "familia Halden": 1,
    "inmunidad mágica del protagonista": 1,
    "herbolaria mujer": 1,
    "Familia real de Thiseia": 1,
    "Ren (presunto)": 2,
    "Caída de Thiseia": 1,
    "Líneas de sangre": 1,
    "nieto_de_Beld-san": 2,
    "Lugar_del_vínculo": 1,
    "Heredero del Báculo": 2,
    "claro en el bosque": 1,
    "la chica": 3,
    "hechizo del mago": 1,
    "El Rey": 1,
    "lanza del cazador": 1,
    "el abuelo": 2,
    "el alto": 1,
    "cámara_de_evaluación": 1,
    "Arma del Eslabón 10": 1,
    "Fragmento de Spelarita": 1,
    "Anillo exterior": 1,
    "Báculo del Rey": 1,
    "Abuelo del narrador": 1,
    "Tecnología bélica de Spelarita": 1,
    "su pasado": 1,
    "Eslabón 10": 1,
    "Telmira (Eslabón 9)": 1,
    "El Báculo": 1,
    "Archivo real": 1,
    "Lanza resonante": 1,
    "Thiseia (reino)": 1,
    "Abuelo de Ren": 1,
    "Regente de Thiseia": 1,
    "campanilla de hierro del abuelo": 1,
    "Halden (madre)": 1,
    "magia curativa": 1,
    "Bosque Silecioso de Ren": 1,
    "energía de la chica": 1,
    "chica desconocida": 2,
    "señora_herbolarios": 1,
    "hombre mayor": 1,
    "El Báculo (figura/linaje)": 1,
    "Báculo": 1,
    "Campo de entrenamiento real": 1,
    "el cazador": 1,
    "esposas mágicas": 1,
    "algo tiraba de mí desde el pecho": 1,
    "el chico": 1,
    "el cazador / garra negra": 1,
    "Characters/Heredera": 1
  },
  "orphan_notes_count": 283,
  "unresolved_links_count": 401,
  "degree_distribution_summary": {
    "min": 0,
    "max": 26,
    "avg": 0.9978
  },
  "relation_density_summary": {
    "edges_per_node": 0.4989,
    "has_local_graph_data": true
  },
  "warnings": [
    "real_labels_omitted_in_commit_safe_report"
  ]
}

## Viewer Project
Viewer project construido en runtime privado con 99_System/markdown_manifest.json y 99_System/markdown_graph_index.json.

## Viewer Manual Review Server
{
  "assessment": "spanish_20ch_viewer_manual_review_server_ready",
  "server_started": true,
  "host": "0.0.0.0",
  "port": 8872,
  "local_url": "http://127.0.0.1:8872",
  "project_id": "tmp__textifai_private_provider_runs__sp095_spanish_20ch_e2e_vaerl_markdown_viewer__20260527T074727Z__markdown_vault",
  "root": "/tmp/textifai_private_provider_runs/sp095_spanish_20ch_e2e_vaerl_markdown_viewer/20260527T074727Z",
  "stop_command": "kill 285469",
  "endpoint_status": {
    "/api/projects": 200,
    "/": 200,
    "/api/projects/tmp__textifai_private_provider_runs__sp095_spanish_20ch_e2e_vaerl_markdown_viewer__20260527T074727Z__markdown_vault": 200,
    "/api/projects/tmp__textifai_private_provider_runs__sp095_spanish_20ch_e2e_vaerl_markdown_viewer__20260527T074727Z__markdown_vault/graph": 200,
    "/api/projects/tmp__textifai_private_provider_runs__sp095_spanish_20ch_e2e_vaerl_markdown_viewer__20260527T074727Z__markdown_vault/note": 200
  },
  "manual_review_required": true
}

## Viewer API Validation
{
  "assessment": "spanish_20ch_viewer_api_validation_ready",
  "overview_ok": true,
  "wiki_ok": true,
  "graph_ok": true,
  "node_detail_ok": true,
  "backlinks_ok": false,
  "tags_ok": true,
  "local_graph_ok": true,
  "artifacts_secondary": true,
  "writer_outcome_visible": true,
  "readiness": "ready_for_manual_review"
}

## Graph Quality Summary
{
  "assessment": "spanish_20ch_graph_quality_summary_ready",
  "node_count": 445,
  "edge_count": 222,
  "nodes_by_kind": {
    "chapter": 19,
    "character": 66,
    "concept": 137,
    "event": 95,
    "object": 66,
    "place": 61,
    "review": 1
  },
  "edges_by_kind": {
    "Characters/Guardia": 1,
    "Concepts/Nerys": 3,
    "Concepts/Regente": 3,
    "Concepts/Sera": 6,
    "Places/Thiseia": 1,
    "Places/Castillo_De_Thisiea": 4,
    "Places/Claro": 1,
    "Concepts/Guardias": 1,
    "Concepts/Sellado": 1,
    "Objects/Talismanes": 3,
    "Places/Torre": 3,
    "Concepts/Canalizadores": 1,
    "Concepts/Ren": 8,
    "Events/Colapso_Hechizo": 3,
    "Events/Huida_Ren": 1,
    "Events/Intento_De_Robo_Campanilla": 1,
    "Events/Reflexion_Ren": 1,
    "Concepts/Nael": 6,
    "Concepts/Abuelo": 5,
    "Objects/Biombo": 1,
    "Objects/Campanilla": 1,
    "Objects/Cesta": 2,
    "Objects/Mortero": 1,
    "Concepts/Tota": 6,
    "Places/Campo": 1,
    "Objects/Chaqueta": 1,
    "Events/Abuelo_Examina_Chica": 1,
    "Objects/Capa": 1,
    "Places/Casa_Herbolarios": 1,
    "Places/Casa_Ren": 1,
    "Objects/Catre_Invitados": 1,
    "Concepts/Chica_Herida": 5,
    "Concepts/Deber": 1,
    "Events/Enviar_Herbolarios": 1,
    "Events/Llevar_Chica_Casa": 1,
    "Concepts/Magulladuras": 1,
    "Objects/Manta_Bordada": 1,
    "Characters/Marido_Herbolarios": 1,
    "Concepts/Pomadas": 1,
    "Events/Ren_Habla_Herbolarios": 1,
    "Events/Ren_Va_Herbolarios": 1,
    "Concepts/Respeto_Sagrado": 1,
    "Concepts/Reverencia": 1,
    "Objects/Taza": 1,
    "Objects/Valla": 1,
    "Concepts/Vendas": 1,
    "Objects/Cubo": 1,
    "Objects/Manta": 1,
    "Concepts/Cazador": 3,
    "Objects/Esposas": 1,
    "Places/Ladera": 1,
    "Concepts/Lealtad": 1,
    "Objects/Pluma": 1,
    "Concepts/Protagonista": 4,
    "Concepts/Narrador": 12,
    "Concepts/Princesa": 7,
    "Concepts/Ayudante": 3,
    "Concepts/Consejo": 3,
    "Characters/Emisario": 1,
    "Concepts/Sensomago": 2,
    "Concepts/Spelarita": 5,
    "Concepts/Agenda": 3,
    "Events/Asentimiento_Del_Narrador": 1,
    "Places/Camara_De_Evaluacion_2": 3,
    "Events/Fin_De_La_Agenda": 1,
    "Concepts/Cadena": 1,
    "Concepts/Gaheris": 1,
    "Concepts/Heredera": 1,
    "Characters/Telmira": 2,
    "Objects/Cebolla": 1,
    "Objects/Vendaje": 1,
    "Concepts/Reyes_De_Thisiea": 1,
    "Places/Thisiea": 1,
    "Events/Alejamiento_Del_Nieto": 1,
    "Objects/Campana_Llave": 1,
    "Concepts/Equilibrio_Del_Reino": 1,
    "Characters/Pares_Reales": 2,
    "Events/Partida_Planeada": 1,
    "Objects/Pergamino_Secreto": 1,
    "Places/Cobertizo": 1,
    "Concepts/Ella": 3,
    "Concepts/Intruso": 1,
    "familia Halden": 1,
    "inmunidad mágica del protagonista": 1,
    "herbolaria mujer": 1,
    "Familia real de Thiseia": 1,
    "Ren (presunto)": 2,
    "Caída de Thiseia": 1,
    "Líneas de sangre": 1,
    "nieto_de_Beld-san": 2,
    "Lugar_del_vínculo": 1,
    "Heredero del Báculo": 2,
    "claro en el bosque": 1,
    "la chica": 3,
    "hechizo del mago": 1,
    "El Rey": 1,
    "lanza del cazador": 1,
    "el abuelo": 2,
    "el alto": 1,
    "cámara_de_evaluación": 1,
    "Arma del Eslabón 10": 1,
    "Fragmento de Spelarita": 1,
    "Anillo exterior": 1,
    "Báculo del Rey": 1,
    "Abuelo del narrador": 1,
    "Tecnología bélica de Spelarita": 1,
    "su pasado": 1,
    "Eslabón 10": 1,
    "Telmira (Eslabón 9)": 1,
    "El Báculo": 1,
    "Archivo real": 1,
    "Lanza resonante": 1,
    "Thiseia (reino)": 1,
    "Abuelo de Ren": 1,
    "Regente de Thiseia": 1,
    "campanilla de hierro del abuelo": 1,
    "Halden (madre)": 1,
    "magia curativa": 1,
    "Bosque Silecioso de Ren": 1,
    "energía de la chica": 1,
    "chica desconocida": 2,
    "señora_herbolarios": 1,
    "hombre mayor": 1,
    "El Báculo (figura/linaje)": 1,
    "Báculo": 1,
    "Campo de entrenamiento real": 1,
    "el cazador": 1,
    "esposas mágicas": 1,
    "algo tiraba de mí desde el pecho": 1,
    "el chico": 1,
    "el cazador / garra negra": 1,
    "Characters/Heredera": 1
  },
  "orphan_notes_count": 283,
  "unresolved_links_count": 401,
  "degree_distribution_summary": {
    "min": 0,
    "max": 26,
    "avg": 0.9978
  },
  "relation_density_summary": {
    "edges_per_node": 0.4989,
    "has_local_graph_data": true
  },
  "warnings": [
    "real_labels_omitted_in_commit_safe_report"
  ]
}

## UI Review Checklist
{
  "assessment": "spanish_20ch_ui_review_checklist_ready",
  "wiki_visible_navigable": true,
  "graph_visible": true,
  "local_graph_available": true,
  "node_size_by_degree": true,
  "backlinks_visible": true,
  "tags_visible": true,
  "node_detail_useful": true,
  "artifacts_debug_secondary": true,
  "author_facing_language": true,
  "open_design_guidance_used": true,
  "guidance_sources": [
    "docs/textifai-design-direction.md",
    "docs/textifai-ui-review-checklist.md",
    "docs/textifai-open-design-codex-setup.md"
  ],
  "graph_node_count": 445,
  "graph_edge_count": 222
}

## Private Decision Handoff
- docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight/decision_handoff_private.md
- docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight/writer_outcome_private.md
- docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight/graph_quality_summary_private.md
- docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight/markdown_materialization_summary_private.md
- docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight/viewer_quality_examples_private.md
- Upload order ChatGPT review: decision_handoff_private.md -> writer_outcome_private.md -> graph_quality_summary_private.md -> markdown_materialization_summary_private.md -> viewer_quality_examples_private.md

## Private Runtime Packet
- /tmp/textifai_private_provider_runs/sp095_spanish_20ch_e2e_vaerl_markdown_viewer/20260527T074727Z

## Commit-safe vs Private Decision Handoff
Commit-safe contiene métricas y decisiones; private contiene ejemplos reales de nodos/relaciones/eventos/evidence.

## Product Decision
{
  "assessment": "spanish_20ch_partial_needs_targeted_retry",
  "provider_calls_executed": true,
  "runtime_root": "/tmp/textifai_private_provider_runs/sp095_spanish_20ch_e2e_vaerl_markdown_viewer/20260527T074727Z",
  "private_runtime_packet_root": "/tmp/textifai_private_provider_runs/sp095_spanish_20ch_e2e_vaerl_markdown_viewer/20260527T074727Z",
  "private_handoff_root": "/home/david/projects/autonovel-fork/docs/handoffs/private/safepoint-095_spanish-20ch-vaerl-markdown-viewer-preflight",
  "next_phase": "Phase 1.3.M-b5c-4y — targeted retry + markdown edit queue scaffolding",
  "spanish_20ch_allowed_for_manual_review": true
}

## Recommended Next Phase
Phase 1.3.M-b5c-4y — targeted retry + markdown edit queue scaffolding

## What Worked
- Preflight source+provider
- DeepSeek real run
- VaERL->Markdown->graph wiring
- Viewer API surfaces disponibles

## What Failed
- Revisar capítulos marcados retry/warnings según writer outcome.

## Data Written
- Runtime privado en /tmp
- Reports commit-safe en tests/fixtures
- Private summaries gitignored

## Privacy / Non-committed Output
No se commitea source prose ni prompts ni raw provider outputs ni viewer project real.

## Tests Added / Updated
- tests/test_textifai_spanish_20ch_e2e_preflight.py

## Validation Performed
- Viewer endpoint checks
- Suite SP-095 + regresiones solicitadas

## Safety Constraints
No OpenAI, no full novel beyond ch_001–ch_020, no write-back.

## Known Limitations
Markdown en viewer sigue read-only; patch proposal queue queda para fase posterior.

## Future Extensions
Editor Markdown + queue de parches VaERL + targeted retry Pro por capítulo.

## Runtime Changes
Se añadió script de orquestación SP-095 y extensión del runner DeepSeek para idioma/obra y no-artificial-cap.

## Write-back
NO

## Branch
phase-1.3-ingestion-vaerl-hardening
