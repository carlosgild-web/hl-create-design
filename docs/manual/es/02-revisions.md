# 02 · Revisiones

*Hilda & Luna Beadworks · Manual de Diseño de Ingeniería Electrónica · Edición 2026.1.
Empresa ficticia; contenido de demostración.*

La letra de revisión identifica una versión de un diseño. El número de diseño más la
revisión identifican exactamente un conjunto de ficheros: `HL-HW-26-0042` revisión `B`.

## La secuencia
<a id="sequence"></a>

`A B C D E F G H J K L M N P R T U V W Y`

Después de `Y` viene `AA`, luego `AB`, `AC`… omitiendo las mismas letras en cada
posición. Veinte revisiones de un mismo diseño es muy raro; si llegas ahí, habla con tu
responsable.

## Letras omitidas
<a id="skipped-letters"></a>

Las letras **I, O, Q, S, X y Z no se usan nunca**, ni en mayúscula ni en minúscula. En un
cajetín impreso, una serigrafía o una etiqueta se confunden fácilmente con otra cosa:

| Letra | Se confunde con |
|---|---|
| `I` | el dígito `1` |
| `O` | el dígito `0` |
| `Q` | `O` o `0` |
| `S` | el dígito `5` |
| `X` | una tachadura o el signo de multiplicar |
| `Z` | el dígito `2` |

Así, después de `H` viene `J`, después de `N` viene `P`, después de `R` viene `T` y
después de `W` viene `Y`.

## La primera revisión
<a id="first-revision"></a>

Un diseño nuevo empieza en la revisión **`A`**. No existen las revisiones `0`, `-`, `01`
ni `P1`. Los prototipos también usan letras, y no hay subrevisiones como `A1` o `A.2`.

## La siguiente revisión
<a id="next-revision"></a>

La siguiente revisión es la letra que sigue en la secuencia a la revisión más alta que
existe. No te saltes letras: después de `C` viene `D`, aunque el cambio sea grande. Create
Design comprueba las revisiones existentes y propone la siguiente letra libre.

## Nunca reutilices una letra
<a id="never-reuse"></a>

Una letra que se creó alguna vez queda usada, aunque se borrara su carpeta o se abandonara
la revisión. Si la revisión `C` se empezó y se abandonó, la siguiente es `D`.

*Por qué:* los PDF de la `C` pueden haber llegado ya al taller o a un proveedor. Dos placas
distintas con el mismo número y la misma letra serían imposibles de distinguir.

## Revisiones y estado en SAP
<a id="revisions-and-status"></a>

| Estado del diseño en SAP | Revisión nueva |
|---|---|
| `IN_WORK` | Permitida |
| `RELEASED` | Permitida, con aviso: el proceso de la empresa exige un número de ECO (esta versión de Create Design no lo comprueba) |
| `BLOCKED` | No permitida |
| `OBSOLETE` | No permitida: usa el diseño sucesor |

Ver [06-sap-statuses](06-sap-statuses.md).

## Comprobación rápida
<a id="quick-check"></a>

| Revisiones existentes | Pedida | ¿Válida? | Por qué |
|---|---|---|---|
| ninguna | `A` | Sí | Los diseños nuevos empiezan en `A` |
| ninguna | `B` | No | Los diseños nuevos empiezan en `A` |
| `A B C D E F G H` | `I` | No | La `I` se omite; la siguiente es `J` |
| `A B C` | `E` | No | No se saltan letras; la siguiente es `D` |
| `A B` | `B` | No | `B` ya existe; las letras no se reutilizan |
| `A B C D E F G H J K L M N` | `P` | Sí | La `O` se omite |
