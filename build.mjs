import { mkdirSync, copyFileSync, writeFileSync, cpSync, rmSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const root = dirname(fileURLToPath(import.meta.url));
const out = join(root, '.vercel', 'output');
const staticDir = join(out, 'static');

rmSync(out, { recursive: true, force: true });
mkdirSync(join(staticDir, 'assets'), { recursive: true });

copyFileSync(join(root, 'index.html'), join(staticDir, 'index.html'));
cpSync(join(root, 'assets'), join(staticDir, 'assets'), { recursive: true });

writeFileSync(
  join(out, 'config.json'),
  JSON.stringify(
    {
      version: 3,
      routes: [
        { handle: 'filesystem' },
        { src: '/(.*)', dest: '/index.html' }
      ]
    },
    null,
    2
  )
);

console.log('Build Output API: wrote .vercel/output/static + config.json');
