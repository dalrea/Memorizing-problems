import { defineConfig } from "vite";

// Set VITE_BASE=/<repo-name>/ when deploying to GitHub Pages under a project page.
// For root-level deployments (Netlify/Vercel/own domain) leave it unset.
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  build: {
    target: "es2020",
    sourcemap: false,
  },
});
