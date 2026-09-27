// Copy the embeddable widget (single source of truth: packages/widget/widget.js)
// into public/ so the web app serves it at /widget.js. The API container can't
// see packages/ (its build context is apps/api), so the public URL serves it here.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../../packages/widget/widget.js");
const dest = resolve(here, "../public/widget.js");

mkdirSync(dirname(dest), { recursive: true });
copyFileSync(src, dest);
console.log(`[copy-widget] ${src} -> ${dest}`);
