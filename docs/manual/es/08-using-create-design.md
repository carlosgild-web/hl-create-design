# 08 · Uso de Create Design

*Hilda & Luna Beadworks · Manual de Diseño de Ingeniería Electrónica · Edición 2026.1.
Empresa ficticia; contenido de demostración.*

Cómo funciona la app Create Design: el panel Inicio, el asistente, las tarjetas de
confirmación y los archivos que crea. Las reglas están en los capítulos 01–06.

## Qué hace Create Design
<a id="what-it-does"></a>

Create Design crea un proyecto de KiCad 9 a partir de la plantilla de la empresa con el
cajetín ya relleno: número de diseño, revisión, material SAP, proyecto, departamento,
diseñador y fecha (ver [03-title-block](03-title-block.md#fields)). Exporta un PDF y una
vista previa, y ofrece el proyecto en .zip y el botón **Abrir en KiCad**.

Palabras clave: qué hace, para qué sirve, aplicación, app, herramienta, genera, purpose, overview, what is this app, proyecto kicad

## Diseño nuevo o desde SAP
<a id="new-or-existing"></a>

En el panel Inicio, elige qué quieres crear:
- **Diseño nuevo** pide un número nuevo a SAP y empieza en la revisión `A`. Úsalo cuando
  cambia la función o la placa no puede sustituir a la anterior.
- **Desde un diseño existente** añade la siguiente revisión a un diseño de SAP. Elige el
  diseño en la lista; departamento, número, nombre y la siguiente revisión se rellenan y
  quedan bloqueados.

Ver [01-design-numbering](01-design-numbering.md#new-number-or-revision).

Palabras clave: diseño nuevo, diseño existente, revisión nueva, número nuevo, cuál elijo, elegir, otra revisión, new design, existing design, new revision

## El panel Inicio
<a id="start-panel"></a>

Para un **Diseño nuevo**, rellena Departamento, Nombre del diseño (en inglés) y Diseñador
(`C. Velazquez`), y pulsa **Obtener número SAP**. SAP da el número, el material y el
proyecto. La descripción es opcional.

Para una revisión nueva, elige el diseño en la lista de SAP. Solo añades el diseñador y, si
quieres, una descripción. Después pulsa **Crear diseño** y confirma la tarjeta.

Palabras clave: empezar, inicio, primeros pasos, qué necesito, campos, datos, ocupo, obtener número sap, reservar, arrancar, llenar, start, what do I need

## El asistente rellena el formulario
<a id="assistant-fills-form"></a>

Describe el diseño en una frase, por ejemplo «revisión C de la placa de visión del
clasificador de cuentas» o «nueva placa controladora para la taladradora, Hardware». El
asistente busca el diseño en SAP y propone los valores del formulario. Revísalos; no se
crea nada hasta que confirmas una tarjeta. **Probar un ejemplo** envía una frase así.

Palabras clave: asistente, ia, rellenar, llenar, formulario, campos, proponer, describir, frase, probar un ejemplo, assistant, fill, autofill

## Paso a paso
<a id="step-by-step"></a>

Pulsa **Guíame paso a paso**. El asistente hace una sola pregunta corta en cada respuesta,
un campo cada vez, y comprueba cada respuesta antes de la siguiente pregunta.

Palabras clave: guíame, guiado, guiar, paso a paso, campo por campo, uno por uno, preguntando, preguntas, wizard, step by step

## Tarjetas de confirmación
<a id="confirmation-cards"></a>

Una tarjeta en el chat muestra lo que va a pasar: reservar un número o crear un diseño. No
pasa nada hasta que pulsas **Confirmar**. **Cancelar** deja todo como estaba. El asistente
puede abrir una tarjeta, pero solo tu clic la ejecuta.

Palabras clave: tarjeta, confirmar, cancelar, botón, clic, dar clic, no pasa nada, chat, card, confirm

## La tarjeta caducó
<a id="card-expired"></a>

Una tarjeta vale 30 minutos. Después dice que caducó y no se puede confirmar. Pídelo de
nuevo al asistente o usa el botón del formulario para obtener una tarjeta nueva.

Palabras clave: caducó, caducada, caduca, vencida, expiró, 30 minutos, cuánto dura, tarde, expired, how long

## Deshacer después de reservar
<a id="undo-number"></a>

**Deshacer** solo quita el número del formulario. La reserva sigue en SAP y el número no se
libera: un número reservado no se vuelve a emitir. Si lo reservaste por error, avisa a tu
responsable (ver [07-faq](07-faq.md#wrong-reservation)).

Palabras clave: deshacer, liberar, liberar número, devolver, cancelar reserva, se liberó, se canceló, undo, release number

## La siguiente revisión libre
<a id="next-free-revision"></a>

La lista de SAP muestra la última revisión que conoce SAP y la siguiente libre, por ejemplo
«última B → rev E». La siguiente letra libre cuenta las revisiones de SAP y las carpetas de
revisión que ya existen, así que las revisiones C y D creadas aquí cuentan aunque SAP solo
muestre la B. Una letra nunca se reutiliza (ver [02-revisions](02-revisions.md#never-reuse)).

Palabras clave: última, siguiente revisión, se salta, se brinca, rev E, por qué no, letra, lista, latest, next revision

## El circuito de ejemplo de la plantilla
<a id="template-circuit"></a>

Todo proyecto nuevo parte de la plantilla de la empresa, que trae un circuito de ejemplo:
una fuente de 24 V a 5 V, 3 A. Demuestra que la hoja y el cajetín funcionan. Bórralo y
dibuja tu circuito. En una revisión nueva, abre la revisión anterior en KiCad y copia su
circuito.

Palabras clave: circuito de ejemplo, plantilla, 24 V, 24V, 5 V, fuente, trae, viene, borrar, borro, esquemático, example circuit, template

## Abrir en KiCad
<a id="open-in-kicad"></a>

**Abrir en KiCad** inicia KiCad 9 en el equipo donde corre Create Design. Si no se inicia,
abre en KiCad 9 el archivo de proyecto que aparece bajo la vista previa (*Archivo › Abrir
proyecto…*) o descarga el proyecto en .zip.

Palabras clave: abrir en kicad, no funcionó, no abre, no se abrió, falla, botón, zip, descargar, open in kicad, didn't work

## No hay PDF ni vista previa
<a id="no-pdf"></a>

El PDF y la vista previa los genera `kicad-cli` (KiCad 9). Si falta o falla, el diseño no se
crea: Create Design no guarda nada, avisa de que falló la exportación del PDF y un número
reservado sigue reservado. Pide al administrador que instale KiCad 9, o que configure
`KICAD_CLI` si KiCad no está en el PATH, y crea el diseño otra vez.

Palabras clave: pdf, vista previa, exportación, falló, kicad-cli, no encuentra, falta, svg, export failed, not found

## Pasos del agente
<a id="agent-steps"></a>

**Pasos del agente** muestra lo que hizo el asistente en cada respuesta: las llamadas al
modelo, las herramientas que usó y los resultados que vio. Sirve para ver por qué respondió
como respondió.

Palabras clave: pasos del agente, pasos, registro, herramientas, qué hizo, cómo veo, agent steps, trace, log

## Modo demostración
<a id="demo-mode"></a>

«Demo mode: no language model is configured» significa que no hay ningún modelo de IA
conectado, así que el asistente no puede responder ni rellenar el formulario. Todo lo demás
funciona: rellena el formulario tú mismo; las comprobaciones, SAP y las tarjetas de
confirmación funcionan igual.

Palabras clave: modo demo, demo mode, demostración, sin ia, sin modelo, modelo de lenguaje, no configurado, significa, fake

## El asistente va lento
<a id="slow-assistant"></a>

Un modelo local (Ollama) puede ir lento en un equipo sin tarjeta gráfica. Espera, pulsa
**Parar** o rellena el formulario directamente: el formulario funciona sin el asistente. Si
el modelo no responde a tiempo, la respuesta se detiene y la app puede ofrecer otro modelo.

Palabras clave: lento, tarda, se agotó el tiempo, tiempo, no responde, no respondió, a tiempo, esperar, parar, ollama, slow, timed out
