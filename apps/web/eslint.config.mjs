import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    rules: {
      "@next/next/no-html-link-for-pages": "off"
    },
    ignores: [
      ".next/**",
      "node_modules/**",
      "src/e2e/**",
      "next-env.d.ts",
      "*.config.ts",
      "*.config.mjs"
    ]
  }
];

export default eslintConfig;
