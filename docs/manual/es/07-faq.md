# 07 · Preguntas frecuentes

*Hilda & Luna Beadworks · Manual de Diseño de Ingeniería Electrónica · Edición 2026.1.
Empresa ficticia; contenido de demostración.*

## ¿Puedo elegir yo el número de diseño?
<a id="own-number"></a>

No. Solo SAP emite números de diseño; reserva uno en Create Design.
Ver [01-design-numbering](01-design-numbering.md#issued-by-sap).

Palabras clave: elegir número, propio número, inventar, ponerle, choose number

## ¿Por qué se rechazó la revisión I?
<a id="revision-i"></a>

`I`, `O`, `Q`, `S`, `X` y `Z` no se usan nunca porque parecen dígitos. Después de `H`
viene `J`. Ver [02-revisions](02-revisions.md#skipped-letters).

Palabras clave: revisión I, letra I, rechazada, no me deja

## Reservé un número por error. ¿Puedo devolverlo?
<a id="wrong-reservation"></a>

No. Un número reservado no se vuelve a emitir, así que queda como un hueco en la
secuencia. Es normal; avisa a tu responsable para que nadie lo use.
Ver [01-design-numbering](01-design-numbering.md#sequence).

Palabras clave: por error, me equivoqué, devolver, regresar, cancelar reserva, departamento equivocado, mistake

## La carpeta de la revisión ya existe. ¿Qué hago?
<a id="folder-exists"></a>

Create Design nunca sobrescribe ficheros. Alguien ya creó esa revisión: crea la siguiente
revisión libre. Ver [04-folder-structure](04-folder-structure.md#revision-folders).

Palabras clave: carpeta existe, ya existe, sobrescribir, folder exists

## ¿Puedo partir de un proyecto antiguo?
<a id="old-project"></a>

No copiando su carpeta: los nombres de fichero y el cajetín quedarían mal. Crea el diseño o
la revisión nueva en Create Design y después copia el circuito en KiCad.
Ver [04-folder-structure](04-folder-structure.md#revision-folders).

Palabras clave: proyecto antiguo, revisión anterior, copiar, reusar, old project

## El diseño está RELEASED. ¿Puedo hacer una revisión nueva?
<a id="released-revision"></a>

Sí, con un aviso: el proceso de la empresa exige un número de ECO. Habla con tu
responsable. Ver [06-sap-statuses](06-sap-statuses.md#released).

Palabras clave: liberado, ECO, released

## El diseño está BLOCKED u OBSOLETE.
<a id="blocked-obsolete"></a>

No puedes crear una revisión. Si está bloqueado, contacta con Ingeniería de Producto
indicando el motivo del bloqueo. Si está obsoleto, trabaja sobre su sucesor.
Ver [06-sap-statuses](06-sap-statuses.md#blocked).

Palabras clave: bloqueado, obsoleto, sucesor, blocked, obsolete

## ¿Por qué el número de material tiene tantos ceros?
<a id="material-zeros"></a>

SAP guarda los números de material con 18 caracteres. El cajetín los muestra sin los
ceros a la izquierda: `000000000040001234` es `40001234`.
Ver [01-design-numbering](01-design-numbering.md#sap-material).

Palabras clave: material, ceros, ceros a la izquierda

## ¿Puedo escribir el nombre del diseño en español?
<a id="name-language"></a>

No. Los nombres de diseño van en inglés y sin tildes, porque llegan a SAP y a documentos
para proveedores. Ver [03-title-block](03-title-block.md#design-name).

Palabras clave: español, acentos, idioma, spanish, accents

## ¿Qué año lleva un número reservado el 31 de diciembre?
<a id="year-end"></a>

El año de la reserva, aunque el trabajo siga en enero.
Ver [01-design-numbering](01-design-numbering.md#year).

Palabras clave: año, diciembre, enero, year

## ¿El asistente crea diseños por su cuenta?
<a id="assistant"></a>

No. El asistente explica las reglas, consulta SAP y propone valores. Crear ficheros o
reservar un número solo ocurre cuando pulsas **Confirmar**. Quien decide si un valor es
válido son las comprobaciones de Create Design, no el asistente, y el asistente puede
equivocarse.

Palabras clave: asistente, ia, por su cuenta, solo, crea, no coinciden, quién decide, válido, razón, marca error, assistant

## SAP no responde.
<a id="sap-down"></a>

Create Design no crea nada sin SAP. Vuelve a intentarlo más tarde.
Ver [06-sap-statuses](06-sap-statuses.md#sap-unavailable).

Palabras clave: sap caído, no responde, sap down

## ¿Cómo escribo el diseñador?
<a id="designer-format"></a>

Inicial, punto, espacio y apellido, como en el directorio de la empresa: `C. Velazquez`. Se
permiten acentos; máximo 40 caracteres. Ver [03-title-block](03-title-block.md#designer).

Palabras clave: diseñador, nombre del diseñador, formato, mi nombre, inicial, apellido, no acepta, rechaza, designer, format

## ¿Dónde están mis archivos?
<a id="where-are-my-files"></a>

Dentro de la raíz de diseños, en `<DEPT>/<NúmeroDeDiseño>/<Rev>/`, por ejemplo
`HW/HL-HW-26-0042/A/`. Los archivos se llaman `<NúmeroDeDiseño>_<Rev>` y el PDF va a
`output/`. Ver [04-folder-structure](04-folder-structure.md#layout).

Palabras clave: archivos, carpeta, dónde, se guardan, se crea, proyecto de kicad, ruta, ubicación, queda, proyecto, pdf, files, folder, where

## ¿Quiénes son los responsables de cada departamento?
<a id="department-leads"></a>

HW: E. Marín · PWR: L. Brandt · EMB: A. Kowalski · TFX: R. Navarro. Pregunta a tu
responsable si dudas qué departamento o número usar. Ver [05-departments](05-departments.md#list).

Palabras clave: responsable, responsables, jefe, a quién le pregunto, contacto, quién es, lead, leads

## ¿Pueden dos diseños tener el mismo nombre?
<a id="same-name"></a>

Create Design no lo impide: lo que identifica un diseño es su número, no su nombre. Antes de
reservar un número nuevo, busca en la lista de SAP de **Desde un diseño existente**. Si la
placa nueva puede sustituir a la anterior, haz una revisión nueva en vez de un número nuevo.
Ver [01-design-numbering](01-design-numbering.md#new-number-or-revision).

Palabras clave: mismo nombre, duplicado, repetir, repetido, se puede repetir, ya existe, ya hay, otro diseño, same name, duplicate
