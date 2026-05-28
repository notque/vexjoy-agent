// no-meta.js — fixture: a .js file with no exported meta.name. Such a file
// does not register; its pipeline (if any) stays prose-only.
export async function run() {}
const meta = 42; // not an exported object, no name key
