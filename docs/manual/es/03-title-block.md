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
| N.º de diseño | `HL-HW-26-0042` | SAP ([01-design-numbering](01-design-numbering.md)) |
| Rev. | `A` | Tú, comprobada con [02-revisions](02-revisions.md) |
| Material SAP | `40001234` | SAP, sin ceros a la izquierda |
| Proyecto | `P-26-0108` | SAP |
| Departamento | `HW – Hardware Design` | [05-departments](05-departments.md) |
| Diseñador | `C. Velazquez` | Tú |
| Fecha | `2026-11-17` | El día en que se creó la revisión |
| Hoja | `1/1` | KiCad |

## Nombre del diseño
<a id="design-name"></a>

El nombre del diseño es el título de todas las hojas y el texto breve del material en SAP.

- **De 3 a 40 caracteres.** 40 es la longitud del texto breve de material en SAP.
- **Caracteres permitidos:** letras `A–Z` y `a–z`, dígitos, espacios, y `-`, `_`, `.`.
  Sin tildes, eñes ni otros símbolos: el nombre va a SAP y a sistemas de proveedores que
  no los admiten.
- **En inglés**, porque el nombre aparece en documentos para proveedores.
- **Se guarda con mayúscula inicial en cada palabra.** Las palabras ya escritas en
  mayúsculas se mantienen (`LED`, `USB`, `24V`). Create Design convierte el nombre por ti:
  `bead drill controller` pasa a `Bead Drill Controller`.
- Se quitan los espacios del principio y del final, y los espacios repetidos quedan en uno.
- **Describe la función.** No pongas en el nombre el número de diseño, la revisión ni
  palabras como `new`, `final` o `copy`. `Kiln Thermocouple Interface` es un buen nombre;
  `HL-HW-26-0042 Rev A` y `New Board Final` no lo son.

## Diseñador
<a id="designer"></a>

Inicial, punto, espacio y apellido, como en el directorio de la empresa: `C. Velazquez`,
`E. Marín`. Aquí sí se admiten tildes. Máximo 40 caracteres.

## Fecha
<a id="date"></a>

Formato ISO 8601, `AAAA-MM-DD`: `2026-11-17`. Nunca `17/11/2026` ni `11/17/2026`, que
significan días distintos según el país.

## Papel y hojas
<a id="paper"></a>

La plantilla usa A4 apaisado. En un esquemático jerárquico todas las hojas usan la misma
plantilla de hoja, así que todas muestran el mismo número de diseño y la misma revisión.

## No hagas esto
<a id="dont"></a>

- No copies el cajetín, ni el proyecto entero, de un diseño antiguo.
- No escribas texto encima del cajetín ni modifiques `hl_title_block.kicad_wks`.
- No cambies el número de diseño ni la revisión en KiCad; crea una revisión nueva.
