import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const result=spawnSync(path.join(root,'.venv','Scripts','python.exe'),['-m','pytest','tests/e2e','-v'],{cwd:root,stdio:'inherit',windowsHide:true});
process.exit(result.status ?? 1);
