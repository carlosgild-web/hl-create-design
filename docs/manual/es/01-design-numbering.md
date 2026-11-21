# 01 · Numeración de diseños

*Hilda & Luna Beadworks · Manual de Diseño de Ingeniería Electrónica · Edición 2026.1.
Empresa ficticia; contenido de demostración.*

Cada diseño electrónico (un proyecto de esquemático y las placas que salen de él) tiene
exactamente un número de diseño. El número identifica el diseño en SAP, en el cajetín, en
el nombre de la carpeta y en cualquier conversación sobre él.

## Formato
<a id="format"></a>

`HL-<DEPT>-<AA>-<NNNN>`

| Parte | Significado | Valores |
|---|---|---|
| `HL` | Prefijo de la empresa | Siempre `HL` |
| `DEPT` | Código de departamento | `HW`, `PWR`, `EMB`, `TFX` (ver [05-departments](05-departments.md)) |
| `AA` | Año en que se reservó el número | Dos cifras, por ejemplo `26` |
| `NNNN` | Secuencia por departamento y año | Cuatro cifras, de `0001` a `9999` |

Ejemplo: `HL-HW-26-0042` es el número 42 que Diseño de Hardware reservó en 2026.

Se escribe en mayúsculas, con guiones y sin espacios. Todos estos son incorrectos:
`hl-hw-26-0042`, `HL-HW-2026-0042`, `HL_HW_26_0042`, `HL-HW-26-42`, `HL-HWD-26-0042`.

Palabras clave: formato, cómo se escribe, cómo es, HL-, código de departamento, otro departamento, pertenece, HW, PWR, format

## Solo SAP emite números
<a id="issued-by-sap"></a>

Nunca inventes un número, no copies el de otro diseño y no cojas «el siguiente» mirando
la lista de carpetas. Reserva el número en Create Design: SAP devuelve a la vez el número
de diseño, el número de material SAP y el proyecto (elemento PEP).

*Por qué:* antes de 2024, dos ingenieros cogiendo «el siguiente» número el mismo día es
como llegaron números duplicados al taller.

Palabras clave: elegir, escoger, inventar, propio número, ponerle, no existe, no encuentra, emite sap, choose, own number

## El año del número
<a id="year"></a>

`AA` es el año en que se **reservó** el número, no el año en que se termina o se libera
el diseño. Nunca cambia: un número reservado el 30 de diciembre de 2025 sigue siendo
`HL-xx-25-NNNN` en todas sus revisiones, también si la revisión C se hace en 2027.

Palabras clave: año, año que viene, año que entra, enero, diciembre, dos dígitos, year

## La secuencia
<a id="sequence"></a>

`NNNN` empieza en `0001` para cada departamento cada año, y SAP emite el siguiente valor
libre. Los huecos son normales: un número reservado que luego no se usa no se vuelve a
emitir. Un número no se reutiliza nunca, ni siquiera el de un diseño cancelado u obsoleto.

Palabras clave: huecos, faltan números, se brincan, se saltan, 0041, 0044, secuencia, gaps

## ¿Número nuevo o revisión nueva?
<a id="new-number-or-revision"></a>

- **Revisión nueva, mismo número:** cambias el mismo diseño (una corrección, un cambio de
  componente, un cambio de rutado) y la placa nueva puede sustituir a la anterior. Ver
  [02-revisions](02-revisions.md).
- **Número nuevo:** cambia la función, es otro producto, o la placa nueva no puede
  sustituir a la anterior. Ingeniería de Producto suele pasar el diseño antiguo a
  `OBSOLETE` con el nuevo como sucesor (ver [06-sap-statuses](06-sap-statuses.md)).

Palabras clave: número nuevo, revisión nueva, cuál, en vez de, sustituir, otro producto, nomás, new number

## Número de material SAP
<a id="sap-material"></a>

Cada número de diseño tiene un material SAP: el conjunto electrónico. El número de material
tiene **18 caracteres con ceros a la izquierda**, en el rango `000000000040000000` a
`000000000049999999` (el rango de conjuntos electrónicos).

- En el cajetín y en los documentos se muestra **sin ceros a la izquierda**: `40001234`.
- En SAP y en el intercambio de datos siempre tiene 18 caracteres: `000000000040001234`.
- Lo asigna SAP junto con el número de diseño. Nunca lo escribas a mano.

Palabras clave: material, número de material, ceros, ceros a la izquierda, 18 caracteres, material sap

## Proyecto (elemento PEP)
<a id="wbs"></a>

Formato `P-<AA>-<NNNN>`, por ejemplo `P-26-0108`. Cada diseño imputa sus horas de
ingeniería a un proyecto. Al reservar un número, SAP usa el proyecto por defecto del
departamento para ese año (ver [05-departments](05-departments.md#default-projects)).
Ingeniería de Producto puede mover el diseño a otro proyecto en SAP más adelante.

Palabras clave: proyecto, wbs, P-26, quién asigna, escoger proyecto, project

## Comprobación rápida
<a id="quick-check"></a>

| Número | ¿Válido? | Por qué |
|---|---|---|
| `HL-PWR-25-0006` | Sí | |
| `HL-HW-26-42` | No | La secuencia lleva cuatro cifras: `0042` |
| `HL-HW-2026-0042` | No | El año lleva dos cifras: `26` |
| `HL-MECH-26-0003` | No | `MECH` no es un departamento de Ingeniería Electrónica |
| `hl-emb-26-0007` | No | Solo mayúsculas |

Palabras clave: mal, no vale, inválido, minúsculas, año de cuatro dígitos, comprobar, wrong
