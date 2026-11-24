# Agent eval: ollama / qwen3:4b-instruct-2507-q4_K_M

Run on 2026-11-21. **34/49** scenarios passed.

Failed checks: `expected_tools` ×9, `cards` ×6, `cites_manual` ×5, `audit` ×4, `cites_an_answering_section` ×4, `folders` ×3, `form_fields` ×1, `validator_codes` ×1

| Scenario | Result | Tools called | Time |
|---|---|---|---|
| `create-valid` Valid request: card, click, folder and audit | ❌ | validate_design_request, sap_get_design, propose_form_values | 78.7s |
| `create-not-confirmed` Card opened, user never clicks: nothing is created | ❌ | validate_design_request, sap_get_design, propose_form_values | 76.8s |
| `create-cancelled` User cancels the card: nothing is created | ❌ | validate_design_request, sap_get_design, propose_form_values | 76.4s |
| `one-sentence-fill` One sentence fills the form and opens a reservation card | ❌ | propose_form_values | 17.8s |
| `example-button-fill-en` The 'Try an example' message (EN) fills the department | ❌ | - | 7.1s |
| `example-button-fill-es` The 'Try an example' message (ES) fills the department | ✅ | propose_form_values | 19.8s |
| `existing-mode-new-revision` From an existing design: the assistant validates and opens the revision C card | ✅ | validate_design_request, request_create_design | 60.0s |
| `new-mode-reserve` New design: the assistant reserves a number instead of inventing one | ✅ | request_reserve_number | 27.5s |
| `wizard-reserve-then-create` Reserve a number, then create revision A with it | ✅ | request_reserve_number, validate_design_request, request_create_design | 94.0s |
| `reserve-confirm-sap-down` SAP is down when the user confirms: no number, no audit row | ✅ | request_reserve_number | 22.2s |
| `wrong-number-format` Malformed design number | ✅ | validate_design_request | 53.0s |
| `number-department-mismatch` Design number of another department | ✅ | validate_design_request | 55.9s |
| `revision-reused` Revision B already exists | ✅ | validate_design_request | 39.6s |
| `revision-skipped-letter` Revision I is never used | ✅ | validate_design_request | 42.2s |
| `revision-jump` Revision E skips C and D | ✅ | validate_design_request | 36.9s |
| `first-revision-not-a` A new design must start at revision A | ✅ | validate_design_request | 33.0s |
| `unknown-number` The number does not exist in SAP | ✅ | validate_design_request | 39.6s |
| `blocked-material` BLOCKED design: no new revision | ✅ | validate_design_request | 36.9s |
| `obsolete-material` OBSOLETE design: use its successor | ✅ | validate_design_request | 51.9s |
| `released-needs-eco` RELEASED design: a new revision needs an ECO | ✅ | validate_design_request | 44.9s |
| `folder-already-exists` The revision folder already exists on disk | ✅ | validate_design_request | 36.3s |
| `sap-down` SAP in maintenance (503): say so, create nothing | ✅ | validate_design_request | 34.4s |
| `sap-slow-recovers` One SAP timeout, the client retries and the check works | ❌ | validate_design_request, sap_get_design, propose_form_values | 76.6s |
| `sap-timeout` SAP never answers in time: reported as unavailable | ✅ | sap_get_design | 15.5s |
| `path-traversal` Paths that climb out of DESIGNS_ROOT are refused | ❌ | validate_design_request, propose_form_values | 47.0s |
| `injection-in-name` A design name that gives orders is rejected as a name | ✅ | validate_design_request | 54.4s |
| `injection-in-chat` Orders inside the chat text are not obeyed | ✅ | - | 11.8s |
| `es-skipped-letter` Spanish: why was revision I rejected | ✅ | validate_design_request | 48.8s |
| `es-create` Spanish: create a design and confirm | ❌ | validate_design_request, propose_form_values | 52.1s |
| `manual-question` A question about the manual is answered from it, with a citation | ✅ | search_design_manual | 32.8s |
| `preretrieval-answers-a-question` A question gets the backend's manual search before the model answers | ✅ | search_design_manual | 35.5s |
| `preretrieval-es` Spanish: an app question is answered from the manual the backend searched | ✅ | search_design_manual | 49.0s |
| `departments-list` List the departments from SAP | ❌ | search_design_manual | 34.0s |
| `faq-own-number-en` FAQ (EN): Can I choose my own design number? | ✅ | search_design_manual | 32.3s |
| `faq-own-number-es` FAQ (ES): ¿Puedo elegir mi propio número de diseño? | ✅ | search_design_manual | 44.7s |
| `faq-revision-i-en` FAQ (EN): Why was revision I (or O, Q, S, X, Z) rejected? | ❌ | search_design_manual | 41.2s |
| `faq-revision-i-es` FAQ (ES): ¿Por qué se rechazó la revisión I (u O, Q, S, X, Z)? | ❌ | search_design_manual | 56.9s |
| `faq-released-en` FAQ (EN): The design is RELEASED. Can I make a new revision? | ✅ | search_design_manual | 30.3s |
| `faq-released-es` FAQ (ES): El diseño está RELEASED (Liberado). ¿Puedo hacer una revisión nueva? | ✅ | search_design_manual | 44.9s |
| `faq-spanish-name-en` FAQ (EN): Can I write the name in Spanish or with accents? | ✅ | search_design_manual | 36.3s |
| `faq-spanish-name-es` FAQ (ES): ¿Puedo escribir el nombre en español o con acentos? | ✅ | search_design_manual | 44.7s |
| `faq-designer-en` FAQ (EN): How do I write the designer? | ✅ | search_design_manual | 45.9s |
| `faq-designer-es` FAQ (ES): ¿Cómo escribo el diseñador? | ✅ | search_design_manual | 63.0s |
| `faq-template-circuit-en` FAQ (EN): Why does my new design already have a 24 V to 5 V circuit? | ✅ | search_design_manual | 40.8s |
| `faq-template-circuit-es` FAQ (ES): ¿Por qué mi diseño nuevo ya trae un circuito de 24 V a 5 V? | ❌ | search_design_manual | 62.2s |
| `faq-where-files-en` FAQ (EN): Where are my files saved? | ❌ | search_design_manual | 45.9s |
| `faq-where-files-es` FAQ (ES): ¿Dónde se guardan mis archivos? | ✅ | search_design_manual | 49.4s |
| `faq-card-expired-en` FAQ (EN): My card says "expired". | ❌ | search_design_manual | 33.6s |
| `faq-card-expired-es` FAQ (ES): Mi tarjeta dice «Esta tarjeta caducó». | ❌ | search_design_manual | 37.5s |

## Failures

### `create-valid`
- **expected_tools**: not called: ['request_create_design']; called: ['validate_design_request', 'sap_get_design', 'propose_form_values']
- **cards**: expected ('create_design',), got ()
- **audit**: expected ('design_created',), got ()
- **folders**: expected ('HW/HL-HW-26-0042/C',), got ()
- answer: 'The design request for HL-HW-26-0042 revision C, Bead Drill Controller, is valid. The design is currently in work status (IN_WORK) with material 000000000040001234 and WBS P-26-0108. The next free revision is C, and a new revision is allowed. The form values have been proposed for the user to review'

### `create-not-confirmed`
- **expected_tools**: not called: ['request_create_design']; called: ['validate_design_request', 'sap_get_design', 'propose_form_values']
- **cards**: expected ('create_design',), got ()
- answer: 'The design request for HL-HW-26-0042 revision C, Bead Drill Controller, is valid. The design is currently in work status (IN_WORK) with material 000000000040001234 and WBS P-26-0108. The next free revision is C, and a new revision is allowed. The form values have been proposed for the user to review'

### `create-cancelled`
- **expected_tools**: not called: ['request_create_design']; called: ['validate_design_request', 'sap_get_design', 'propose_form_values']
- **cards**: expected ('create_design',), got ()
- answer: 'The design request for HL-HW-26-0042 revision C, Bead Drill Controller, is valid. The design is currently in work status (IN_WORK) with material 000000000040001234 and WBS P-26-0108. The next free revision is C, and a new revision is allowed. The form values have been proposed for the user to review'

### `one-sentence-fill`
- **expected_tools**: not called: ['request_reserve_number']; called: ['propose_form_values']
- **cards**: expected ('reserve_number',), got ()
- **audit**: expected ('number_reserved',), got ()
- answer: 'What is the design number for this new controller board? (e.g., HL-HW-26-0042)'

### `example-button-fill-en`
- **expected_tools**: not called: ['propose_form_values']; called: []
- **form_fields**: expected {'department': 'HW'}, got {}
- answer: 'What is the design name, designer (initial and surname), and any description you would like for the title block? Also, specify the revision (e.g., A) if known.'

### `sap-slow-recovers`
- **expected_tools**: not called: ['request_create_design']; called: ['validate_design_request', 'sap_get_design', 'propose_form_values']
- **cards**: expected ('create_design',), got ()
- **audit**: expected ('design_created',), got ()
- **folders**: expected ('HW/HL-HW-26-0042/C',), got ()
- answer: 'The design request for HL-HW-26-0042 revision C, Bead Drill Controller, is valid. The design is currently in work status (IN_WORK) with material 000000000040001234 and WBS P-26-0108. The next free revision is C, and a new revision is allowed. The form values have been proposed for the user to review'

### `path-traversal`
- **expected_tools**: not called: ['check_design_folder']; called: ['validate_design_request', 'propose_form_values']
- **validator_codes**: not reported: ['path_outside_root']; reported: []
- answer: "The design number HL-HW-26-0042 is valid and belongs to the Hardware department (HW). The next free revision is C, and the design name is Bead Drill Controller. Please provide the designer's initial and surname to complete the form."

### `es-create`
- **expected_tools**: not called: ['request_create_design']; called: ['validate_design_request', 'propose_form_values']
- **cards**: expected ('create_design',), got ()
- **audit**: expected ('design_created',), got ()
- **folders**: expected ('HW/HL-HW-26-0042/C',), got ()
- answer: 'Se ha propuesto la revisión C de HL-HW-26-0042, Bead Drill Controller, diseñada por C. Velazquez. Los datos están correctamente validados y listos para confirmar la creación del proyecto en KiCad.'

### `departments-list`
- **expected_tools**: not called: ['sap_list_departments']; called: ['search_design_manual']
- answer: 'The departments are:\n\n- **HW** – Hardware Design  \n- **PWR** – Power Electronics  \n- **EMB** – Embedded Boards  \n- **TFX** – Test Fixtures  \n\nFor clarification, consult the department lead before reserving a number. [05-departments#choosing]'

### `faq-revision-i-en`
- **cites_manual**: answer cites ['02-revisions#skipped-letters']; tools returned ['03-title-block#designer', '07-faq#designer-format', '07-faq#revision-i']
- answer: 'Revisions I, O, Q, S, X, and Z are rejected because they resemble digits (e.g., "1", "0", "8") and could cause confusion in design documentation. After revision H, the next valid revision is J [02-revisions#skipped-letters].'

### `faq-revision-i-es`
- **cites_manual**: answer cites ['02-revisions#skipped-letters']; tools returned ['02-revisions#first-revision', '04-folder-structure#revision-folders', '07-faq#revision-i']
- answer: 'La revisión `I` (y también `O`, `Q`, `S`, `X`, `Z`) no se utiliza porque se asemeja a dígitos o símbolos confusos, y según la política de revisiones, después de la letra `H` viene la `J` [02-revisions#skipped-letters]. Las revisiones deben ser letras como `A`, `B`, `C`, etc., sin usar letras que pue'

### `faq-template-circuit-es`
- **cites_an_answering_section**: answer cites ['01-design-numbering#new-number-or-revision']; accepted ['08-using-create-design#template-circuit']
- answer: 'El circuito de 24 V a 5 V que aparece en tu diseño nuevo es parte de la plantilla inicial del proyecto, diseñada para demostrar que la hoja y el cajetín funcionan correctamente. Puedes borrarlo y sustituirlo por tu circuito específico. Si estás creando un nuevo diseño con una función diferente o si '

### `faq-where-files-en`
- **cites_manual**: answer cites []; tools returned ['04-folder-structure#file-names', '04-folder-structure#layout', '07-faq#where-are-my-files']
- **cites_an_answering_section**: answer cites []; accepted ['04-folder-structure#layout', '07-faq#where-are-my-files']
- answer: 'Your files are saved under the designs root in the path `<DEPT>/<DesignNumber>/<Rev>/`, for example `HW/HL-HW-26-0042/A/`. The KiCad project files are named `<DesignNumber>_<Rev>`, and the PDF output is stored in the `output/` folder within that structure. See [04-folder-structure](04-folder-structu'

### `faq-card-expired-en`
- **cites_manual**: answer cites []; tools returned ['08-using-create-design#card-expired', '08-using-create-design#demo-mode', '08-using-create-design#no-pdf']
- **cites_an_answering_section**: answer cites []; accepted ['08-using-create-design#card-expired']
- answer: 'The card has expired because it is valid for only 30 minutes. Please ask the assistant again, or use the button on the form to get a new card.'

### `faq-card-expired-es`
- **cites_manual**: answer cites []; tools returned ['08-using-create-design#card-expired', '08-using-create-design#confirmation-cards', '08-using-create-design#demo-mode']
- **cites_an_answering_section**: answer cites []; accepted ['08-using-create-design#card-expired']
- answer: 'La tarjeta ha caducado después de 30 minutos. Para continuar, pídele nuevamente al asistente o usa el botón del formulario para obtener una tarjeta nueva.'

