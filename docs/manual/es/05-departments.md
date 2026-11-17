# 05 · Departamentos

*Hilda & Luna Beadworks · Manual de Diseño de Ingeniería Electrónica · Edición 2026.1.
Empresa ficticia; contenido de demostración.*

Hilda & Luna Beadworks fabrica cuentas de vidrio artesanales. Su departamento de
Ingeniería Electrónica diseña la electrónica de las máquinas del taller: taladros, hornos,
bombos de pulido, clasificación e inspección. Tiene cuatro subdepartamentos, y cada uno
tiene el código que se usa en el número de diseño.

## Los cuatro departamentos
<a id="list"></a>

| Código | Nombre | Qué diseña | Responsable |
|---|---|---|---|
| `HW` | Diseño de Hardware (*Hardware Design*) | Placas de control e interfaz: controladores de taladro, interfaces de horno, estaciones de inspección | E. Marín |
| `PWR` | Electrónica de Potencia (*Power Electronics*) | Fuentes de alimentación, drivers de motor, drivers de resistencias, alimentación de respaldo | L. Brandt |
| `EMB` | Placas Embebidas (*Embedded Boards*) | Placas con microcontrolador: nodos de sensores, pantallas, pasarelas | A. Kowalski |
| `TFX` | Utillajes de Prueba (*Test Fixtures*) | Útiles de prueba, racks de burn-in y útiles de calibración para las placas anteriores | R. Navarro |

## ¿Qué departamento?
<a id="choosing"></a>

Elige según la función principal de la placa:

- Un driver de motor con un pequeño microcontrolador es `PWR` si la etapa de potencia es
  lo esencial de la placa.
- Un útil de prueba es siempre `TFX`, aunque lleve una fuente de alimentación o un
  procesador.
- Si dudas, pregunta al responsable del departamento **antes** de reservar el número. El
  código forma parte del número, y un número nunca cambia.

## En el cajetín
<a id="title-block-format"></a>

El departamento se muestra como código, raya corta (–) y nombre en inglés:
`HW – Hardware Design`.

## Proyectos por defecto
<a id="default-projects"></a>

Al reservar un número, SAP lo imputa al proyecto por defecto (elemento PEP) del
departamento para ese año:

| Departamento | Proyecto por defecto 2026 |
|---|---|
| `HW` | `P-26-0108` |
| `PWR` | `P-26-0112` |
| `EMB` | `P-26-0115` |
| `TFX` | `P-26-0121` |

Ingeniería de Producto puede mover después un diseño a un proyecto de cliente o de
inversión.
