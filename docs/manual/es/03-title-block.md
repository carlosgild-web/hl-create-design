# 03 · Cajetín

*Hilda & Luna Beadworks · Manual de Diseño de Ingeniería Electrónica · Edición 2026.1.
Empresa ficticia; contenido de demostración.*

Todas las hojas del esquemático usan la plantilla de hoja de la empresa,
`hl_title_block.kicad_wks`. Create Design rellena los campos al crear el proyecto. No los
escribas a mano en el diálogo *Configurar página* de KiCad: los valores vienen de SAP y de
este manual.

## Campos
<a id="fields"></a>

| Campo | Ejemplo | Origen |
|---|---|---|
| Logo y empresa | Hilda & Luna Beadworks | La plantilla |
| Título | `Bead Drill Controller` | Tú: el nombre del diseño |
| Descripción (opcional) | `Accionamiento paso a paso de seis ejes` | Tú |
| N.º de diseño | `HL-HW-26-0042` | SAP ([01-design-numbering](01-design-numbering.md)) |
| Rev. | `A` | Tú, comprobada con [02-revisions](02-revisions.md) |
| Material SAP | `40001234` | SAP, sin ceros a la izquierda |
| Proyecto | `P-26-0108` | SAP |
| Departamento | `HW – Hardware Design` | [05-departments](05-departments.md) |
| Diseñador | `C. Velazquez` | Tú |
| Fecha | `2026-11-17` | El día en que se creó la revisión |
| Hoja | `1/1` | KiCad |

Palabras clave: cajetín, campos, qué se rellena, title block

## Nombre del diseño
<a id="design-name"></a>

El nombre del diseño es el título de todas las hojas y el texto breve del material en SAP.

- **De 3 a 40 caracteres.**
- **Solo** `A–Z`, `a–z`, dígitos, espacios y `- _ .`: sin tildes, eñes ni otros símbolos,
  que SAP y los proveedores no admiten.
- **En inglés**: aparece en documentos de proveedores.
- **Mayúscula inicial** en cada palabra y en cada parte de una palabra con guion
  (`bead drill controller` → `Bead Drill Controller`, `burn-in` → `Burn-In`). Se mantienen
  las palabras con mayúsculas (`LED`, `24V`, `USB-C`, `LEDs`). Se quitan los espacios de más.
- **Describe la función.** Sin número de diseño ni palabras de versión: `new` o `final`
  al principio, `new`, `final` o `copy` al final, o `rev`/`revision` + una letra o un
  número (`Rev A`). `HL-HW-26-0042 Rev A` y `New Board Final` se rechazan. En medio
  solo dan un aviso: `Copy Stand Controller` vale.

Palabras clave: reglas del nombre, nombre del diseño, largo, qué tan largo, caracteres, se permiten, mayúsculas, mayúscula inicial, new, final, copy, palabra, rechaza, name rules

## Nombre de un diseño existente
<a id="name-from-sap"></a>

Una revisión nueva conserva el nombre que el diseño ya tiene en SAP. El nombre es el texto
breve del material de SAP, así que todas las revisiones de un diseño llevan el mismo título.

- Si el número de diseño existe en SAP, el nombre del diseño **debe ser el de SAP** (con el
  formato de arriba: mayúscula inicial en cada palabra, espacios simples). Create Design lo
  rellena y lo bloquea.
- Para dar otro nombre a un diseño, pide al responsable del departamento un número de diseño
  nuevo. El nombre de un material existente nunca se cambia desde un cajetín.

Palabras clave: nombre bloqueado, no me deja editar, cambiar el nombre, cambiarle el nombre, renombrar, diseño existente, locked name

## Descripción
<a id="description"></a>

Una línea opcional, en cursiva pequeña, debajo del título. Sirve para decir para qué es este
diseño o esta revisión cuando el nombre no basta: `Accionamiento paso a paso de seis ejes`,
`Rev C: segunda fuente para el driver de puerta`.

- **Opcional**, como máximo **60 caracteres**, en una línea.
- Se admite cualquier idioma y las tildes: a diferencia del nombre, no va a SAP.
- Se quitan los espacios del principio y del final, y los espacios repetidos quedan en uno.
- No se admiten tabuladores ni otros caracteres de control, ni `${`, que KiCad leería como
  una variable de texto y sustituiría por otro campo.
- En KiCad es el *Comentario 1* del cajetín (`${COMMENT1}`).

Palabras clave: descripción, opcional, 60 caracteres, español, qué tan larga, description

## Diseñador
<a id="designer"></a>

Una o dos iniciales con punto, un espacio y el apellido, como en el directorio de la
empresa: `C. Velazquez`, `J. C. Pérez`, `E. Marín`. Las partículas pueden ir en minúscula
(`de`, `del`, `de la`, `de los`, `van`, `von`, `y`): `C. de la Torre`, `M. van Dijk`. La
última palabra del apellido empieza con mayúscula. Se admiten tildes, apóstrofos y guiones
(`L. O'Brien`, `R. Navarro-Ruiz`); los dígitos no. Máximo 40 caracteres.

Palabras clave: diseñador, nombre del diseñador, formato, inicial, apellido, no me acepta, designer

## Fecha
<a id="date"></a>

Formato ISO 8601, `AAAA-MM-DD`: `2026-11-17`. Nunca `17/11/2026` ni `11/17/2026`, que
significan días distintos según el país.

Palabras clave: fecha, date

## Papel y hojas
<a id="paper"></a>

La plantilla usa A4 apaisado. En un esquemático jerárquico todas las hojas usan la misma
plantilla de hoja, así que todas muestran el mismo número de diseño y la misma revisión.

Palabras clave: papel, tamaño de hoja, A4, A3, hojas, paper

## No hagas esto
<a id="dont"></a>

- No copies el cajetín, ni el proyecto entero, de un diseño antiguo.
- No escribas texto encima del cajetín ni modifiques `hl_title_block.kicad_wks`.
- No cambies el número de diseño ni la revisión en KiCad; crea una revisión nueva.

Palabras clave: configuración de página, editar cajetín, cambiar revisión en kicad, directo en kicad, kicad_wks, modificar, hoja, page settings
