# 06 · SAP design statuses

*Hilda & Luna Beadworks · Electronics Engineering Design Manual · Edition 2026.1.
Fictional company; demo content.*

Every design number has a status in SAP. The status decides whether Create Design may
create a new revision.

## Overview
<a id="overview"></a>

| Status | Meaning | New revision | What to do |
|---|---|---|---|
| `IN_WORK` | Being designed, not released | Allowed | Nothing special |
| `RELEASED` | Released for production | Allowed, with a warning | Get an ECO number (company process) |
| `BLOCKED` | On hold by Product Engineering | Not allowed | Contact Product Engineering |
| `OBSOLETE` | Replaced, no longer built | Not allowed | Use the successor design |

Keywords: status, statuses, in work, released, blocked, obsolete, estado, estados

## IN_WORK
<a id="in-work"></a>

The design is being developed and hasn't been released to production. New revisions can
be created freely, following [02-revisions](02-revisions.md).

Keywords: in work, in progress, en trabajo, en curso

## RELEASED
<a id="released"></a>

The design is released and boards are being built from it. A new revision changes what
the workshop builds, so the company process requires an engineering change order (ECO)
number before the new revision is released. This version of Create Design does not check
ECO numbers: it creates the revision and shows a warning. Tell your lead.

Keywords: released, ECO, new revision of released, liberado, revisión de un diseño liberado

## BLOCKED
<a id="blocked"></a>

Product Engineering has put the design on hold, for example because of a quality problem
in field units, a failed safety test or a supplier issue. SAP shows the reason. No new
revision can be created until the block is lifted. Contact Product Engineering and quote
the design number and the block reason.

Keywords: blocked, block reason, product engineering, bloqueado, motivo del bloqueo, ingeniería de producto

## OBSOLETE
<a id="obsolete"></a>

The design has been replaced and is no longer built. SAP names the successor design.
Work on the successor instead: look it up and create a revision there. If there is no
successor and you need the old function again, reserve a new number.

Keywords: obsolete, successor, use successor, obsoleto, sucesor, usar el sucesor

## Who changes the status
<a id="who-changes"></a>

Product Engineering changes statuses in SAP. Create Design only reads them; it never
releases, blocks or makes a design obsolete.

Keywords: change status, release a design, who changes, product engineering, cambiar estado, liberar un diseño, quién cambia

## When SAP is not available
<a id="sap-unavailable"></a>

If SAP doesn't answer (maintenance, network problems), Create Design can't check the
design number and doesn't create anything. Nothing is created or reserved halfway. Try
again later; during SAP maintenance the message says *service unavailable (503)*.

Keywords: sap down, not answering, timeout, 503, error, sap caído, no responde, no contesta, se cae, tiempo de espera
