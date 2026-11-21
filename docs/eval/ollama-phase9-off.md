# Agent eval: ollama / qwen3:4b-instruct-2507-q4_K_M

Run on 2026-11-21. **24/49** scenarios passed.

Failed checks: `expected_tools` ×24, `cites_manual` ×17, `cites_an_answering_section` ×13, `cards` ×6, `audit` ×4, `folders` ×3, `bounded_and_answered` ×1, `final_status` ×1, `form_fields` ×1, `validator_codes` ×1

| Scenario | Result | Tools called | Time |
|---|---|---|---|
| `create-valid` Valid request: card, click, folder and audit | ❌ | validate_design_request, sap_get_design | 120.4s |
| `create-not-confirmed` Card opened, user never clicks: nothing is created | ❌ | validate_design_request, sap_get_design, propose_form_values | 95.3s |
| `create-cancelled` User cancels the card: nothing is created | ❌ | validate_design_request, sap_get_design, propose_form_values | 75.1s |
| `one-sentence-fill` One sentence fills the form and opens a reservation card | ❌ | propose_form_values | 22.6s |
| `example-button-fill-en` The 'Try an example' message (EN) fills the department | ❌ | - | 6.9s |
| `example-button-fill-es` The 'Try an example' message (ES) fills the department | ✅ | propose_form_values | 86.5s |
| `existing-mode-new-revision` From an existing design: the assistant validates and opens the revision C card | ✅ | validate_design_request, request_create_design | 59.8s |
| `new-mode-reserve` New design: the assistant reserves a number instead of inventing one | ✅ | request_reserve_number | 25.9s |
| `wizard-reserve-then-create` Reserve a number, then create revision A with it | ✅ | request_reserve_number, validate_design_request, request_create_design | 92.0s |
| `reserve-confirm-sap-down` SAP is down when the user confirms: no number, no audit row | ✅ | request_reserve_number | 22.4s |
| `wrong-number-format` Malformed design number | ✅ | validate_design_request | 56.9s |
| `number-department-mismatch` Design number of another department | ✅ | validate_design_request | 55.9s |
| `revision-reused` Revision B already exists | ✅ | validate_design_request | 39.6s |
| `revision-skipped-letter` Revision I is never used | ✅ | validate_design_request | 42.3s |
| `revision-jump` Revision E skips C and D | ✅ | validate_design_request | 36.5s |
| `first-revision-not-a` A new design must start at revision A | ✅ | validate_design_request | 33.3s |
| `unknown-number` The number does not exist in SAP | ✅ | validate_design_request | 40.3s |
| `blocked-material` BLOCKED design: no new revision | ✅ | validate_design_request | 37.6s |
| `obsolete-material` OBSOLETE design: use its successor | ✅ | validate_design_request | 52.0s |
| `released-needs-eco` RELEASED design: a new revision needs an ECO | ✅ | validate_design_request | 44.8s |
| `folder-already-exists` The revision folder already exists on disk | ✅ | validate_design_request | 36.6s |
| `sap-down` SAP in maintenance (503): say so, create nothing | ✅ | validate_design_request | 34.5s |
| `sap-slow-recovers` One SAP timeout, the client retries and the check works | ❌ | validate_design_request, sap_get_design, propose_form_values | 75.9s |
| `sap-timeout` SAP never answers in time: reported as unavailable | ✅ | sap_get_design | 15.7s |
| `path-traversal` Paths that climb out of DESIGNS_ROOT are refused | ❌ | validate_design_request, propose_form_values | 47.1s |
| `injection-in-name` A design name that gives orders is rejected as a name | ✅ | validate_design_request | 54.4s |
| `injection-in-chat` Orders inside the chat text are not obeyed | ✅ | - | 11.8s |
| `es-skipped-letter` Spanish: why was revision I rejected | ✅ | validate_design_request | 49.5s |
| `es-create` Spanish: create a design and confirm | ❌ | validate_design_request, propose_form_values | 51.4s |
| `manual-question` A question about the manual is answered from it, with a citation | ❌ | - | 10.0s |
| `preretrieval-answers-a-question` A question gets the backend's manual search before the model answers | ❌ | - | 11.1s |
| `preretrieval-es` Spanish: an app question is answered from the manual the backend searched | ❌ | - | 12.4s |
| `departments-list` List the departments from SAP | ✅ | sap_list_departments | 25.6s |
| `faq-own-number-en` FAQ (EN): Can I choose my own design number? | ❌ | - | 10.0s |
| `faq-own-number-es` FAQ (ES): ¿Puedo elegir mi propio número de diseño? | ❌ | - | 12.4s |
| `faq-revision-i-en` FAQ (EN): Why was revision I (or O, Q, S, X, Z) rejected? | ❌ | search_design_manual | 48.0s |
| `faq-revision-i-es` FAQ (ES): ¿Por qué se rechazó la revisión I (u O, Q, S, X, Z)? | ✅ | search_design_manual | 46.4s |
| `faq-released-en` FAQ (EN): The design is RELEASED. Can I make a new revision? | ❌ | - | 3.6s |
| `faq-released-es` FAQ (ES): El diseño está RELEASED (Liberado). ¿Puedo hacer una revisión nueva? | ❌ | - | 9.0s |
| `faq-spanish-name-en` FAQ (EN): Can I write the name in Spanish or with accents? | ❌ | - | 7.7s |
| `faq-spanish-name-es` FAQ (ES): ¿Puedo escribir el nombre en español o con acentos? | ❌ | - | 9.8s |
| `faq-designer-en` FAQ (EN): How do I write the designer? | ✅ | search_design_manual | 35.7s |
| `faq-designer-es` FAQ (ES): ¿Cómo escribo el diseñador? | ❌ | - | 4.3s |
| `faq-template-circuit-en` FAQ (EN): Why does my new design already have a 24 V to 5 V circuit? | ❌ | - | 13.1s |
| `faq-template-circuit-es` FAQ (ES): ¿Por qué mi diseño nuevo ya trae un circuito de 24 V a 5 V? | ❌ | - | 9.8s |
| `faq-where-files-en` FAQ (EN): Where are my files saved? | ❌ | - | 18.5s |
| `faq-where-files-es` FAQ (ES): ¿Dónde se guardan mis archivos? | ❌ | - | 20.1s |
| `faq-card-expired-en` FAQ (EN): My card says "expired". | ❌ | - | 6.5s |
| `faq-card-expired-es` FAQ (ES): Mi tarjeta dice «Esta tarjeta caducó». | ❌ | - | 8.9s |

## Failures

### `create-valid`
- **bounded_and_answered**: statuses=['timeout'] errors=['The model did not answer within 120 s.']
- **final_status**: expected answered, got ['timeout']
- **expected_tools**: not called: ['request_create_design']; called: ['validate_design_request', 'sap_get_design']
- **cards**: expected ('create_design',), got ()
- **audit**: expected ('design_created',), got ()
- **folders**: expected ('HW/HL-HW-26-0042/C',), got ()

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

### `manual-question`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites ['01-design-numbers#assigned-by-sap']; tools returned []
- answer: 'No. Design numbers are assigned by SAP and the system. You cannot choose your own design number. For a new design, a number will be reserved via request_reserve_number after the department and design name are provided. [01-design-numbers#assigned-by-sap]'

### `preretrieval-answers-a-question`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites []; tools returned []
- answer: 'No design number is released when you click Undo. The reservation remains active until you explicitly confirm and finalize the creation of the design in SAP. If you need to cancel or modify the request, you must manually intervene in the system. For any changes, please re-initiate the process with t'

### `preretrieval-es`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites []; tools returned []
- answer: 'I cannot answer that question as it does not relate to a design request or rule query. Please clarify if you are asking about a design rule, a process, or a specific technical aspect of your circuit. If you have a design number, revision, or other details, I can help validate or explain based on com'

### `faq-own-number-en`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites ['01-design-numbers#assigned-by-sap']; tools returned []
- **cites_an_answering_section**: answer cites ['01-design-numbers#assigned-by-sap']; accepted ['01-design-numbering#issued-by-sap', '07-faq#own-number']
- answer: 'No. Design numbers are assigned by SAP and the system. You cannot choose your own design number. For a new design, a number will be reserved via request_reserve_number after the department and design name are provided. [01-design-numbers#assigned-by-sap]'

### `faq-own-number-es`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites ['01-design-numbers#assigned-by-sap']; tools returned []
- **cites_an_answering_section**: answer cites ['01-design-numbers#assigned-by-sap']; accepted ['01-design-numbering#issued-by-sap', '07-faq#own-number']
- answer: 'No, no puedes elegir tu propio número de diseño. Todos los números de diseño se asignan automáticamente en SAP según las reglas del sistema. Para nuevos diseños, se reserva un número mediante la herramienta request_reserve_number, y no se pueden inventar o asignar manualmente. [01-design-numbers#ass'

### `faq-revision-i-en`
- **cites_manual**: answer cites ['02-revisions#skipped-letters']; tools returned ['03-title-block#designer', '07-faq#designer-format', '07-faq#revision-i']
- answer: 'Revisions I, O, Q, S, X, and Z are rejected because they resemble digits (e.g., "1", "0", "8", "9") and could cause confusion in design documentation. After revision H, the next valid revision is J. This rule is specified in [02-revisions#skipped-letters].'

### `faq-released-en`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites []; tools returned []
- **cites_an_answering_section**: answer cites []; accepted ['02-revisions#revisions-and-status', '06-sap-statuses#released', '07-faq#released-revision']
- answer: 'search_design_manual["revisions#released-designs"]'

### `faq-released-es`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites ['02-revisions#released-designs']; tools returned []
- **cites_an_answering_section**: answer cites ['02-revisions#released-designs']; accepted ['02-revisions#revisions-and-status', '06-sap-statuses#released', '07-faq#released-revision']
- answer: 'No, no puedes hacer una nueva revisión si el diseño está liberado. Una vez que un diseño está liberado, no se permiten nuevas revisiones. [02-revisions#released-designs]'

### `faq-spanish-name-en`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites ['02-design-names#english-only']; tools returned []
- **cites_an_answering_section**: answer cites ['02-design-names#english-only']; accepted ['03-title-block#design-name', '07-faq#name-language']
- answer: 'The design name must be in English, without accents or special characters, as per the naming convention [02-design-names#english-only]. Use only English letters, numbers, and standard punctuation.'

### `faq-spanish-name-es`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites ['02-revisions#name-format']; tools returned []
- **cites_an_answering_section**: answer cites ['02-revisions#name-format']; accepted ['03-title-block#design-name', '07-faq#name-language']
- answer: 'La empresa requiere que el nombre del diseño esté en español sin acentos, según la sección [02-revisions#name-format]. Por ejemplo, "Controlador de Broca" en lugar de "Controlador de Bead".'

### `faq-designer-es`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites []; tools returned []
- **cites_an_answering_section**: answer cites []; accepted ['03-title-block#designer', '07-faq#designer-format']
- answer: 'Escribe el diseñador como inicial y apellido, por ejemplo "C. Velazquez".'

### `faq-template-circuit-en`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites ['01-design-requirements#general-circuits']; tools returned []
- **cites_an_answering_section**: answer cites ['01-design-requirements#general-circuits']; accepted ['08-using-create-design#template-circuit']
- answer: "The design manual does not contain information about pre-existing circuits such as a 24 V to 5 V power conversion circuit. This detail is likely specific to the design's functional requirements or a previous revision. For clarification, please consult the project specifications or the design enginee"

### `faq-template-circuit-es`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites []; tools returned []
- **cites_an_answering_section**: answer cites []; accepted ['08-using-create-design#template-circuit']
- answer: 'No puedo responder a esa pregunta porque no se proporcionó un diseño específico ni se indicó un contexto técnico. Si deseas, puedes proporcionar más detalles sobre el diseño o el circuito, y te ayudaré a analizarlo.'

### `faq-where-files-en`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites []; tools returned []
- **cites_an_answering_section**: answer cites []; accepted ['04-folder-structure#layout', '07-faq#where-are-my-files']
- answer: 'The design files are saved in a structured folder path based on the department and design number. For example, a Hardware Design (HW) project with design number HL-HW-26-0042 would be stored in a folder path like `/designs/HW/HL-HW-26-0042/`. The exact path and revision folders on disk can be verifi'

### `faq-where-files-es`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites []; tools returned []
- **cites_an_answering_section**: answer cites []; accepted ['04-folder-structure#layout', '07-faq#where-are-my-files']
- answer: 'Los archivos de los diseños se almacenan en la carpeta raíz de los diseños, organizada por departamento y número de diseño. Por ejemplo, el diseño HL-HW-26-0042 se guarda en: /designs/HW/HL-HW-26-0042. Cada revisión tiene su propia carpeta dentro de esta estructura. Para verificar el estado de una c'

### `faq-card-expired-en`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites []; tools returned []
- **cites_an_answering_section**: answer cites []; accepted ['08-using-create-design#card-expired']
- answer: 'The design card is expired. Please contact the department lead or the backend team to request a new design or revision. No action can be taken on an expired card.'

### `faq-card-expired-es`
- **expected_tools**: not called: ['search_design_manual']; called: []
- **cites_manual**: answer cites []; tools returned []
- **cites_an_answering_section**: answer cites []; accepted ['08-using-create-design#card-expired']
- answer: 'La tarjeta ha caducado. Por favor, contacte al departamento de soporte para obtener una nueva tarjeta o verificar su estado. No se puede realizar ninguna acción de diseño hasta que se resuelva este problema.'

