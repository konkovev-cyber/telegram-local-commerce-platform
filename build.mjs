import { mkdirSync, copyFileSync, cpSync } from 'fs';

mkdirSync('/vercel/output', { recursive: true });
copyFileSync('/vercel/project/index.html', '/vercel/output/index.html');
cpSync('/vercel/project/assets', '/vercel/output/assets', { recursive: true });
cpSync('/vercel/project/api', '/vercel/output/api', { recursive: true });
console.log('Done');
