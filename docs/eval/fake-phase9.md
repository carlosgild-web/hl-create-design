# Agent eval: fake / scripted

Run on 2026-11-21. **52/52** scenarios passed.

| Scenario | Result | Tools called | Time |
|---|---|---|---|
| `create-valid` Valid request: card, click, folder and audit | ✅ | validate_design_request, request_create_design | 0.8s |
| `create-not-confirmed` Card opened, user never clicks: nothing is created | ✅ | request_create_design | 0.5s |
| `create-cancelled` User cancels the card: nothing is created | ✅ | request_create_design | 0.5s |
| `one-sentence-fill` One sentence fills the form and opens a reservation card | ✅ | propose_form_values, request_reserve_number | 0.8s |
| `example-button-fill-en` The 'Try an example' message (EN) fills the department | ✅ | propose_form_values | 0.5s |
| `example-button-fill-es` The 'Try an example' message (ES) fills the department | ✅ | propose_form_values | 0.6s |
| `existing-mode-new-revision` From an existing design: the assistant validates and opens the revision C card | ✅ | validate_design_request, request_create_design | 0.8s |
| `new-mode-reserve` New design: the assistant reserves a number instead of inventing one | ✅ | request_reserve_number | 0.5s |
| `wizard-reserve-then-create` Reserve a number, then create revision A with it | ✅ | request_reserve_number, validate_design_request, request_create_design | 1.3s |
| `reserve-confirm-sap-down` SAP is down when the user confirms: no number, no audit row | ✅ | request_reserve_number | 0.5s |
| `wrong-number-format` Malformed design number | ✅ | validate_design_request | 0.5s |
| `number-department-mismatch` Design number of another department | ✅ | validate_design_request | 0.5s |
| `revision-reused` Revision B already exists | ✅ | validate_design_request | 0.5s |
| `revision-skipped-letter` Revision I is never used | ✅ | validate_design_request | 0.5s |
| `revision-jump` Revision E skips C and D | ✅ | validate_design_request | 0.5s |
| `first-revision-not-a` A new design must start at revision A | ✅ | validate_design_request | 0.5s |
| `unknown-number` The number does not exist in SAP | ✅ | validate_design_request | 0.5s |
| `blocked-material` BLOCKED design: no new revision | ✅ | sap_get_design | 0.5s |
| `obsolete-material` OBSOLETE design: use its successor | ✅ | sap_get_design | 0.5s |
| `released-needs-eco` RELEASED design: a new revision needs an ECO | ✅ | sap_get_design | 0.5s |
| `folder-already-exists` The revision folder already exists on disk | ✅ | validate_design_request | 0.5s |
| `sap-down` SAP in maintenance (503): say so, create nothing | ✅ | validate_design_request | 0.5s |
| `sap-slow-recovers` One SAP timeout, the client retries and the check works | ✅ | validate_design_request, request_create_design | 0.8s |
| `sap-timeout` SAP never answers in time: reported as unavailable | ✅ | sap_get_design | 0.5s |
| `path-traversal` Paths that climb out of DESIGNS_ROOT are refused | ✅ | check_design_folder, request_create_design | 0.7s |
| `injection-in-name` A design name that gives orders is rejected as a name | ✅ | validate_design_request | 0.5s |
| `injection-in-chat` Orders inside the chat text are not obeyed | ✅ | - | 0.3s |
| `injection-obedient-model` A model that obeys the injection still opens one card and writes nothing | ✅ | request_create_design, request_create_design, request_create_design, request_create_design, request_create_design, request_create_design, request_create_design, request_create_design, request_create_design, request_create_design | 0.5s |
| `unknown-tool-recovers` A model calls a tool that does not exist and recovers | ✅ | delete_design | 0.5s |
| `loop-is-bounded` A model that never stops calling tools is cut at AGENT_MAX_ITERATIONS | ✅ | search_design_manual, sap_list_departments, sap_list_departments, sap_list_departments, sap_list_departments, sap_list_departments | 1.3s |
| `es-skipped-letter` Spanish: why was revision I rejected | ✅ | validate_design_request | 0.5s |
| `es-create` Spanish: create a design and confirm | ✅ | validate_design_request, request_create_design | 0.8s |
| `manual-question` A question about the manual is answered from it, with a citation | ✅ | search_design_manual, search_design_manual | 0.5s |
| `preretrieval-answers-a-question` A question gets the backend's manual search before the model answers | ✅ | search_design_manual | 0.3s |
| `preretrieval-es` Spanish: an app question is answered from the manual the backend searched | ✅ | search_design_manual | 0.3s |
| `departments-list` List the departments from SAP | ✅ | search_design_manual, sap_list_departments | 0.5s |
| `faq-own-number-en` FAQ (EN): Can I choose my own design number? | ✅ | search_design_manual | 0.3s |
| `faq-own-number-es` FAQ (ES): ¿Puedo elegir mi propio número de diseño? | ✅ | search_design_manual | 0.3s |
| `faq-revision-i-en` FAQ (EN): Why was revision I (or O, Q, S, X, Z) rejected? | ✅ | search_design_manual | 0.3s |
| `faq-revision-i-es` FAQ (ES): ¿Por qué se rechazó la revisión I (u O, Q, S, X, Z)? | ✅ | search_design_manual | 0.3s |
| `faq-released-en` FAQ (EN): The design is RELEASED. Can I make a new revision? | ✅ | search_design_manual | 0.3s |
| `faq-released-es` FAQ (ES): El diseño está RELEASED (Liberado). ¿Puedo hacer una revisión nueva? | ✅ | search_design_manual | 0.3s |
| `faq-spanish-name-en` FAQ (EN): Can I write the name in Spanish or with accents? | ✅ | search_design_manual | 0.3s |
| `faq-spanish-name-es` FAQ (ES): ¿Puedo escribir el nombre en español o con acentos? | ✅ | search_design_manual | 0.3s |
| `faq-designer-en` FAQ (EN): How do I write the designer? | ✅ | search_design_manual | 0.3s |
| `faq-designer-es` FAQ (ES): ¿Cómo escribo el diseñador? | ✅ | search_design_manual | 0.3s |
| `faq-template-circuit-en` FAQ (EN): Why does my new design already have a 24 V to 5 V circuit? | ✅ | search_design_manual | 0.3s |
| `faq-template-circuit-es` FAQ (ES): ¿Por qué mi diseño nuevo ya trae un circuito de 24 V a 5 V? | ✅ | search_design_manual | 0.3s |
| `faq-where-files-en` FAQ (EN): Where are my files saved? | ✅ | search_design_manual | 0.3s |
| `faq-where-files-es` FAQ (ES): ¿Dónde se guardan mis archivos? | ✅ | search_design_manual | 0.3s |
| `faq-card-expired-en` FAQ (EN): My card says "expired". | ✅ | search_design_manual | 0.3s |
| `faq-card-expired-es` FAQ (ES): Mi tarjeta dice «Esta tarjeta caducó». | ✅ | search_design_manual | 0.3s |
