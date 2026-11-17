# 05 · Departments

*Hilda & Luna Beadworks · Electronics Engineering Design Manual · Edition 2026.1.
Fictional company; demo content.*

Hilda & Luna Beadworks makes handmade glass beads. Its Electronics Engineering department
(*Ingeniería Electrónica*) designs the electronics for the workshop's machines: drills,
kilns, tumblers, sorting and inspection. It has four sub-departments, and each has the
code used in the design number.

## The four departments
<a id="list"></a>

| Code | Name | What it designs | Lead |
|---|---|---|---|
| `HW` | Hardware Design | Control and interface boards: drill controllers, kiln interfaces, inspection stations | E. Marín |
| `PWR` | Power Electronics | Power supplies, motor drivers, heater drivers, battery backup | L. Brandt |
| `EMB` | Embedded Boards | Microcontroller boards: sensor nodes, displays, gateways | A. Kowalski |
| `TFX` | Test Fixtures | Test jigs, burn-in racks and calibration fixtures for the boards above | R. Navarro |

## Which department?
<a id="choosing"></a>

Choose by the main function of the board:

- A motor driver with a small microcontroller is `PWR` if the power stage is the point
  of the board.
- A test fixture is always `TFX`, even if it contains a power supply or a processor.
- When in doubt, ask the department lead **before** reserving the number. The code is
  part of the number, and a number never changes.

## On the title block
<a id="title-block-format"></a>

The department is shown as code, en dash and English name: `HW – Hardware Design`.

## Default projects
<a id="default-projects"></a>

When a number is reserved, SAP books it to the department's default project (WBS
element) for the year:

| Department | 2026 default project |
|---|---|
| `HW` | `P-26-0108` |
| `PWR` | `P-26-0112` |
| `EMB` | `P-26-0115` |
| `TFX` | `P-26-0121` |

Product Engineering can move a design to a customer or investment project later.
