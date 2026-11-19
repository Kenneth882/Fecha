import { defineConfig } from "vitest/config";

export default defineConfig({
  // tsconfig.json's `@/*` path, as Next.js resolves it.
  resolve: { tsconfigPaths: true },
  test: {
    environment: "node",
    include: ["**/*.test.ts"],
    exclude: ["node_modules/**", ".next/**"],
  },
});
