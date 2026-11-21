# Create Design · Preguntas y respuestas para el asistente

Material base para el asistente de Create Design. Cada respuesta se apoya en el Manual de
Diseño (`docs/manual/es/`) o en el código actual. La línea `Ref:` es el ancla del manual que
el asistente debe citar (las anclas son iguales en inglés y en español). Las respuestas sobre el uso de
la app citan el capítulo 08 (`08-using-create-design`). El test `backend/tests/test_faq_retrieval.py` comprueba
que cada pregunta encuentra su sección (preguntas y paráfrasis en
`backend/app/evals/faq_questions.json`).

---

## 1. Primeros pasos

### ¿Qué hace Create Design?
Crea un proyecto de KiCad 9 a partir de la plantilla de la empresa con el cajetín ya relleno:
número de diseño, revisión, material SAP, proyecto, departamento, diseñador y fecha. Exporta
un PDF y una vista previa, y ofrece un .zip y el botón **Abrir en KiCad**.
Ref: 03-title-block#fields

### ¿Diseño nuevo o revisión nueva? ¿Cuál elijo?
- **Revisión nueva (mismo número):** cambia el mismo diseño (una corrección, un cambio de
  componente o de layout) y la placa nueva puede sustituir a la anterior. Elige **Desde un
  diseño existente**.
- **Número nuevo:** cambia la función, es otro producto o la placa nueva no puede sustituir a
  la anterior. Elige **Diseño nuevo**.
Ref: 01-design-numbering#new-number-or-revision

### ¿Qué necesito para empezar un diseño nuevo?
Departamento, un nombre de diseño en inglés y tu nombre como diseñador (`C. Velazquez`). SAP
da el número, el material y el proyecto cuando pulsas **Obtener número SAP**. La descripción
es opcional.
Ref: 08-using-create-design#start-panel

### ¿Qué necesito para una revisión nueva?
Elige el diseño en la lista de SAP del panel Inicio. Departamento, número, nombre y la
siguiente revisión se rellenan y quedan bloqueados. Solo añades el diseñador y, si quieres,
una descripción.
Ref: 03-title-block#name-from-sap

### ¿El asistente puede rellenar el formulario por mí?
Sí. Describe el diseño en una frase («revisión C de la placa de visión del clasificador de
cuentas» o «nueva placa controladora para la taladradora, Hardware») y propone los valores.
Tú los revisas y pulsas **Confirmar**.
Ref: 08-using-create-design#assistant-fills-form

### ¿Me puede guiar campo por campo?
Sí: pulsa **Guíame paso a paso**. Hace una sola pregunta corta en cada respuesta.
Ref: 08-using-create-design#step-by-step

### ¿El asistente crea algo por su cuenta?
No. Explica las reglas, consulta SAP y propone valores. Un número se reserva, o se crean
archivos, solo cuando pulsas **Confirmar** en una tarjeta. Las comprobaciones del código
deciden si un valor es válido, no el asistente, y el asistente puede equivocarse.
Ref: 07-faq#assistant

---

## 2. Números de diseño

### ¿Puedo elegir mi propio número de diseño?
No. Solo SAP emite números. Usa **Obtener número SAP** (diseño nuevo) o elige un diseño
existente.
Ref: 01-design-numbering#issued-by-sap

### ¿Qué formato tiene un número de diseño?
`HL-<DEPT>-<AA>-<NNNN>`, por ejemplo `HL-HW-26-0042`: mayúsculas, guiones, sin espacios, el
año con dos dígitos y la secuencia con cuatro.
Ref: 01-design-numbering#format

### ¿Por qué `HL-HW-26-42` (o `hl-hw-26-0042`, `HL-HW-2026-0042`) está mal?
La secuencia lleva cuatro dígitos (`0042`), las letras van en mayúsculas y el año lleva dos
dígitos (`26`).
Ref: 01-design-numbering#quick-check

### ¿Por qué dice que mi número «no existe en SAP»?
Solo se pueden usar números que emitió SAP. Revisa si hay una errata o reserva un número nuevo.
Ref: 01-design-numbering#issued-by-sap

### ¿Por qué dice que el número «pertenece al departamento HW, no a PWR»?
El código del departamento forma parte del número. Un número reservado para un departamento
no se puede usar en otro.
Ref: 01-design-numbering#format

### ¿Qué año lleva el número? El trabajo sigue el año que viene.
El año en que se reservó el número. Nunca cambia, tampoco en revisiones posteriores.
Ref: 01-design-numbering#year

### Veo huecos en los números (0041 y luego 0044). ¿Pasa algo?
No. Un número reservado y no usado no se vuelve a emitir, así que los huecos son normales.
Ref: 01-design-numbering#sequence

### Reservé un número por error. ¿Puedo devolverlo?
No. Queda como hueco. Avisa a tu responsable para que nadie lo use.
Ref: 07-faq#wrong-reservation

### Pulsé **Deshacer** después de reservar. ¿Se liberó el número?
No. **Deshacer** solo quita el número del formulario. La reserva sigue en SAP.
Ref: 08-using-create-design#undo-number

---

## 3. Revisiones

### ¿Por qué se rechazó la revisión `I` (u `O`, `Q`, `S`, `X`, `Z`)?
Estas letras no se usan nunca porque se confunden con dígitos o marcas: después de `H` va
`J`, después de `N` va `P`, después de `R` va `T` y después de `W` va `Y`.
Ref: 02-revisions#skipped-letters

### ¿Cuál es la secuencia completa de revisiones?
`A B C D E F G H J K L M N P R T U V W Y`, y después `AA`, `AB`, `AC`…
Ref: 02-revisions#sequence

### ¿Puedo empezar en la revisión 0, 01, P1 o `-`?
No. Todo diseño nuevo empieza en `A`, también los prototipos, y no hay subrevisiones como `A1`.
Ref: 02-revisions#first-revision

### El cambio es grande. ¿Puedo saltar de C a F?
No. Después de `C` va `D`, sea cual sea el tamaño del cambio. El formulario muestra la
siguiente letra libre.
Ref: 02-revisions#next-revision

### La revisión C se abandonó y se borró su carpeta. ¿Puedo reutilizar la C?
No. Una letra que se creó alguna vez queda usada; la siguiente es `D`.
Ref: 02-revisions#never-reuse

### La lista de SAP dice «última B → rev E». ¿Por qué no C?
Las revisiones C y D ya se crearon en Create Design. La siguiente letra libre cuenta tanto las
revisiones que conoce SAP como las carpetas de revisión que existen, y una letra nunca se
reutiliza.
Ref: 08-using-create-design#next-free-revision, 02-revisions#never-reuse

### La carpeta de la revisión ya existe. ¿Qué hago?
Create Design nunca sobrescribe archivos. Alguien ya creó esa revisión; crea la siguiente libre.
Ref: 04-folder-structure#revision-folders

---

## 4. Estado en SAP

### El diseño está RELEASED (Liberado). ¿Puedo hacer una revisión nueva?
Sí, con un aviso. El proceso de la empresa exige un número de ECO antes de liberar la revisión.
Create Design no lo comprueba; avisa a tu responsable.
Ref: 06-sap-statuses#released

### El diseño está BLOCKED (Bloqueado). ¿Qué hago?
No puedes crear una revisión. Contacta con Ingeniería de Producto con el número de diseño y
el motivo del bloqueo que muestra SAP.
Ref: 06-sap-statuses#blocked

### El diseño está OBSOLETE (Obsoleto). ¿Qué hago?
Trabaja en el sucesor que indica SAP (**Usar el sucesor** en el panel Inicio). Si no hay
sucesor y necesitas otra vez esa función, reserva un número nuevo.
Ref: 06-sap-statuses#obsolete

### ¿Puedo cambiar aquí el estado de un diseño?
No. Ingeniería de Producto cambia los estados en SAP; Create Design solo los lee.
Ref: 06-sap-statuses#who-changes

### SAP no responde (503, tiempo de espera agotado). ¿Qué pasa?
No se crea ni se reserva nada, ni siquiera a medias. Inténtalo más tarde.
Ref: 06-sap-statuses#sap-unavailable

---

## 5. Nombre, descripción y diseñador

### ¿Qué reglas tiene el nombre del diseño?
De 3 a 40 caracteres; letras A–Z, dígitos, espacios y `- _ .`; sin acentos; en inglés;
describe la función. Se guarda con cada palabra en mayúscula inicial.
Ref: 03-title-block#design-name

### ¿Por qué mi nombre pasó de `bead drill controller` a `Bead Drill Controller`?
Los nombres se guardan con mayúscula inicial en cada palabra. Las palabras ya escritas en
mayúsculas (`LED`, `USB`, `24V`) se mantienen.
Ref: 03-title-block#design-name

### ¿Por qué no puedo usar «New», «Final» o «Copy» en el nombre?
El nombre describe la función. Las palabras de versión y el número de diseño van en otro sitio.
Ref: 03-title-block#design-name

### ¿Puedo escribir el nombre en español o con acentos?
No. Los nombres van a SAP y a documentos de proveedores. Usa la descripción para texto en
español.
Ref: 07-faq#name-language

### ¿Pueden dos diseños tener el mismo nombre?
Create Design no lo impide: lo que identifica un diseño es su número. Antes de reservar un
número nuevo, busca en la lista de SAP de **Desde un diseño existente**. Si la placa puede
sustituir a la anterior, lo que quieres es una revisión nueva, no un número nuevo.
Ref: 07-faq#same-name

### ¿Por qué el nombre está bloqueado en una revisión nueva?
Una revisión nueva conserva el nombre que tiene SAP. Para otro nombre, pide a tu responsable
un número nuevo.
Ref: 03-title-block#name-from-sap

### ¿Para qué sirve la descripción?
Una línea opcional (máximo 60 caracteres) en cursiva pequeña bajo el título, por ejemplo
«Rev C: segunda fuente para el driver de puerta». Se permiten acentos y español. No se
permite `${`.
Ref: 03-title-block#description

### ¿Cómo escribo el diseñador?
Inicial, punto, espacio y apellido, como en el directorio de la empresa: `C. Velazquez`. Se
permiten acentos; máximo 40 caracteres.
Ref: 03-title-block#designer, 07-faq#designer-format

### ¿Por qué el número de material tiene tantos ceros?
SAP guarda 18 caracteres; el cajetín lo muestra sin ceros a la izquierda:
`000000000040001234` es `40001234`.
Ref: 01-design-numbering#sap-material

### ¿De dónde sale el proyecto (P-26-0108)?
SAP asigna el proyecto por defecto del departamento para ese año. Ingeniería de Producto puede
cambiarlo después.
Ref: 05-departments#default-projects

---

## 6. Departamentos

### ¿Qué departamento elijo?
Según la función principal de la placa. HW: placas de control e interfaz. PWR: fuentes y
drivers de motor y de calefactor. EMB: placas con microcontrolador. TFX: utillajes y bancos de
prueba (siempre TFX, aunque lleven fuente o procesador). Si dudas, pregunta al responsable
antes de reservar.
Ref: 05-departments#choosing

### ¿Quiénes son los responsables de cada departamento?
HW: E. Marín · PWR: L. Brandt · EMB: A. Kowalski · TFX: R. Navarro.
Ref: 05-departments#list

### Elegí mal el departamento después de reservar. ¿Puedo cambiarlo?
No. El código forma parte del número y un número nunca cambia. Reserva un número nuevo en el
departamento correcto y avisa a tu responsable del que no se usará.
Ref: 05-departments#choosing, 07-faq#wrong-reservation

---

## 7. Archivos, PDF y KiCad

### ¿Por qué mi diseño nuevo ya trae un circuito de 24 V a 5 V?
Es el circuito de ejemplo de la plantilla; demuestra que la hoja y el cajetín funcionan.
Bórralo y dibuja tu circuito. En una revisión nueva, copia el circuito de la revisión anterior
en KiCad.
Ref: 08-using-create-design#template-circuit

### ¿Dónde se guardan mis archivos?
`<raíz de diseños>/<DEPT>/<NúmeroDeDiseño>/<Rev>/`, con archivos llamados
`<NúmeroDeDiseño>_<Rev>`. El PDF y el SVG van a `output/`.
Ref: 04-folder-structure#layout

### ¿Puedo guardar el proyecto en el escritorio o en otra unidad?
No. Todo queda dentro de la raíz de diseños. Se rechazan las rutas absolutas, `..` y las
letras de unidad.
Ref: 04-folder-structure#designs-root

### ¿Cómo sigo a partir de mi revisión anterior?
Crea aquí la revisión nueva, abre los dos proyectos en KiCad y copia el contenido del
esquemático. No copies la carpeta entera.
Ref: 04-folder-structure#revision-folders

### **Abrir en KiCad** no funcionó.
Abre en KiCad 9 el archivo de proyecto que aparece bajo la vista previa (*Archivo › Abrir
proyecto…*). También puedes descargar el proyecto en .zip.
Ref: 08-using-create-design#open-in-kicad

### No hay PDF ni vista previa.
El PDF necesita `kicad-cli` (KiCad 9). Sin él, el diseño no se crea: no se guarda nada y un
número reservado sigue reservado. Avisa al administrador, que instala KiCad 9 o configura
`KICAD_CLI` si KiCad no está en el PATH.
Ref: 08-using-create-design#no-pdf

### ¿Puedo editar el cajetín en la Configuración de página de KiCad?
No. Los valores vienen de SAP y del manual. Para cambiar el número o la revisión, crea una
revisión nueva; nunca edites `hl_title_block.kicad_wks`.
Ref: 03-title-block#dont

---

## 8. Tarjetas, asistente y errores

### ¿Qué es la tarjeta que aparece en el chat?
Una tarjeta de confirmación. No pasa nada hasta que pulsas **Confirmar**; **Cancelar** deja
todo como estaba.
Ref: 08-using-create-design#confirmation-cards

### Mi tarjeta dice «Esta tarjeta caducó».
Las tarjetas caducan a los 30 minutos. Pídelo de nuevo o usa el botón del formulario para
obtener una tarjeta nueva.
Ref: 08-using-create-design#card-expired

### ¿Qué son los «Pasos del agente»?
Un registro de lo que hizo el asistente: llamadas al modelo, herramientas usadas y sus
resultados. Sirve para ver por qué respondió como respondió.
Ref: 08-using-create-design#agent-steps

### El asistente solo responde «Demo mode: no language model is configured».
No hay ningún modelo de IA conectado, así que el asistente no puede responder ni rellenar el
formulario. Todo lo demás funciona: rellena el formulario tú mismo; las comprobaciones, SAP y
las tarjetas de confirmación funcionan igual.
Ref: 08-using-create-design#demo-mode

### El asistente va lento o dice que se agotó el tiempo.
El modelo local (Ollama) puede ser lento en CPU. Espera, pulsa **Parar** o rellena el
formulario directamente: el formulario funciona sin el asistente.
Ref: 08-using-create-design#slow-assistant

### El asistente y el formulario no coinciden. ¿Cuál tiene razón?
Las comprobaciones del formulario. El asistente solo explica sus resultados y puede
equivocarse.
Ref: 07-faq#assistant
