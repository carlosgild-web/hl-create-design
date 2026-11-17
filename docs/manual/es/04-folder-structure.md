# 04 · Estructura de carpetas

*Hilda & Luna Beadworks · Manual de Diseño de Ingeniería Electrónica · Edición 2026.1.
Empresa ficticia; contenido de demostración.*

## Estructura
<a id="layout"></a>

```text
<raíz de diseños>/
  HW/
    HL-HW-26-0042/
      A/
        HL-HW-26-0042_A.kicad_pro
        HL-HW-26-0042_A.kicad_sch
        hl_title_block.kicad_wks
        output/
          HL-HW-26-0042_A.pdf
      B/
        ...
  PWR/
  EMB/
  TFX/
```

Una carpeta por departamento, una por número de diseño y una por revisión.

## La raíz de diseños
<a id="designs-root"></a>

Todos los diseños viven bajo una única carpeta raíz: la unidad compartida de ingeniería en
la empresa, y `DESIGNS_ROOT` en Create Design. Nada se guarda fuera de ella.

Create Design rechaza cualquier ruta que salga de la raíz: rutas absolutas, `..`, letras
de unidad como `C:` y enlaces que apunten fuera.

*Por qué:* se perdieron diseños guardados en escritorios y unidades personales, y nadie
encontraba la última revisión.

## Nombres de fichero
<a id="file-names"></a>

Los ficheros se llaman `<NúmeroDeDiseño>_<Rev>`, por ejemplo `HL-HW-26-0042_A.kicad_sch`.
El nombre del diseño nunca forma parte de un nombre de fichero o carpeta: los nombres
pueden cambiar, los números no, y los nombres llevan espacios.

## Una carpeta por revisión
<a id="revision-folders"></a>

Create Design crea la carpeta de una revisión una sola vez, a partir de la plantilla de la
empresa. Si la carpeta ya existe, se detiene y no cambia nada: nunca sobrescribe ficheros.
Elige la siguiente revisión libre ([02-revisions](02-revisions.md#next-revision)).

Para continuar desde la revisión anterior, abre los dos proyectos en KiCad y copia el
contenido del esquemático en el nuevo. No copies la carpeta entera: los nombres de fichero
y el cajetín serían los de la revisión antigua.

## La carpeta output
<a id="output"></a>

`output/` contiene el PDF y el SVG generados. Vuelve a generarlos después de un cambio; no
los edites.

## No hagas esto
<a id="dont"></a>

- Nada de espacios, tildes ni palabras como `final`, `v2` o `copia` en los nombres de
  carpeta.
- No guardes copias personales de un diseño fuera de la raíz de diseños.
- No renombres ni muevas carpetas de diseño a mano.
