import { defineConfig } from "@hey-api/openapi-ts";

const args = process.argv.slice(2);
const host = args[0] || "localhost:8203";

export default defineConfig({
  input: host.includes("http")
    ? `${host}/openapi.json`
    : `http://${host}/openapi.json`,
  output: {
    indexFile: true,
    path: "src/client",
    format: "biome",
  },
  plugins: [
    {
      name: "@hey-api/typescript",
      enums: "javascript",
      readOnlyWriteOnlyBehavior: "off",
    },
  ],
});
