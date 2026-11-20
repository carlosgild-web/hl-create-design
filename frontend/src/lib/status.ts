// Status colors (decision 0014 addendum): in work = brand blue, released = done,
// blocked = error, obsolete = neutral. Sea is kept for "this value came from SAP".
export const STATUS_STYLE: Record<string, string> = {
  IN_WORK: 'bg-hl-cobalt-soft text-hl-cobalt dark:bg-hl-cobalt/30 dark:text-hl-moon',
  RELEASED: 'bg-success/15 text-success',
  BLOCKED: 'bg-destructive/10 text-destructive',
  OBSOLETE: 'bg-muted text-muted-foreground line-through',
}
