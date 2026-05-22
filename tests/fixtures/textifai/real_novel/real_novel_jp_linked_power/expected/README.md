# Expected usefulness artifacts

Este fixture valida utilidad realista sobre novela japonesa:
- entidades relevantes
- relación mágica enlazada
- alias/descriptores útiles
- objeto persistente
- evento/facts importantes
- suppression de pronombres/ruido

Los contratos son amplios y no exigen output exacto frágil.

## Provider / prompt audit artifacts

- `provider_comparison_checklist.json`: comparación sample manual vs replay curado.
- `provider_extraction_gap_report.json`: gaps observados del sample manual.
- `provider_dual_comparison_checklist.json`: checklist post-output para replay curado vs Codex blind vs ChatGPT opcional.
- `prompt_packet_audit_report.json`: estado del packet blind, anti-leakage y readiness.

Estos archivos sí pueden contener expectativas semánticas porque no se envían dentro del prompt RAW.
