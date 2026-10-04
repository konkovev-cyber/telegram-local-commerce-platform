import { mkdirSync, copyFileSync, cpSync } from 'fs';

mkdirSync('/vercel/output', { recursive: true });
copyFileSync('/vercel/path0/index.html', '/vercel/output/index.html');
cpSync('/vercel/path0/assets', '/vercel/output/assets', { recursive: true });
cpSync('/vercel/path0/api', '/vercel/output/api', { recursive: true });
console.log('Done');
