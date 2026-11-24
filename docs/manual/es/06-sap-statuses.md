# 06 · Estados del diseño en SAP

*Hilda & Luna Beadworks · Manual de Diseño de Ingeniería Electrónica · Edición 2026.1.
Empresa ficticia; contenido de demostración.*

Cada número de diseño tiene un estado en SAP. El estado decide si Create Design puede
crear una revisión nueva.

## Resumen
<a id="overview"></a>

| Estado | Significado | Revisión nueva | Qué hacer |
|---|---|---|---|
| `IN_WORK` | En diseño, no liberado | Permitida | Nada especial |
| `RELEASED` | Liberado para producción | Permitida, con aviso | Conseguir un número de ECO (proceso de la empresa) |
| `BLOCKED` | Bloqueado por Ingeniería de Producto | No permitida | Contactar con Ingeniería de Producto |
| `OBSOLETE` | Sustituido, ya no se fabrica | No permitida | Usar el diseño sucesor |

Palabras clave: estado, estados, en trabajo, liberado, bloqueado, obsoleto, status

## IN_WORK
<a id="in-work"></a>

El diseño está en desarrollo y no se ha liberado a producción. Se pueden crear revisiones
nuevas libremente, siguiendo [02-revisions](02-revisions.md).

Palabras clave: en trabajo, en curso, in work

## RELEASED
<a id="released"></a>

El diseño está liberado y se fabrican placas a partir de él. Una revisión nueva cambia lo
que fabrica el taller, así que el proceso de la empresa exige un número de orden de cambio
de ingeniería (ECO) antes de liberar la revisión nueva. Esta versión de Create Design no
comprueba números de ECO: crea la revisión y muestra un aviso. Avisa a tu responsable.

Palabras clave: liberado, released, ECO, revisión de un diseño liberado, revisar

## BLOCKED
<a id="blocked"></a>

Ingeniería de Producto ha bloqueado el diseño, por ejemplo por un problema de calidad en
unidades instaladas, una prueba de seguridad fallida o un problema con un proveedor. SAP
muestra el motivo. No se puede crear ninguna revisión hasta que se levante el bloqueo.
Contacta con Ingeniería de Producto indicando el número de diseño y el motivo del bloqueo.

Palabras clave: bloqueado, blocked, motivo del bloqueo, ingeniería de producto

## OBSOLETE
<a id="obsolete"></a>

El diseño se ha sustituido y ya no se fabrica. SAP indica el diseño sucesor. Trabaja sobre
el sucesor: búscalo y crea la revisión allí. Si no hay sucesor y vuelves a necesitar la
función antigua, reserva un número nuevo.

Palabras clave: obsoleto, obsolete, sucesor, usar el sucesor, ahora qué

## Quién cambia el estado
<a id="who-changes"></a>

Ingeniería de Producto cambia los estados en SAP. Create Design solo los lee; nunca
libera, bloquea ni deja obsoleto un diseño.

Palabras clave: cambiar estado, liberar un diseño, libero, quién cambia, quién puede, ingeniería de producto, change status

## Cuando SAP no está disponible
<a id="sap-unavailable"></a>

Si SAP no responde (mantenimiento, problemas de red), Create Design no puede comprobar el
número de diseño y no crea nada. Nada se queda creado ni reservado a medias. Vuelve a
intentarlo más tarde; durante el mantenimiento de SAP el mensaje dice *servicio no
disponible (503)*.

Palabras clave: sap caído, no responde, no contesta, se cae, tiempo de espera, 503, error, sap down
