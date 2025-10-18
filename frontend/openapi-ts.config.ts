import { defineConfig } from "@hey-api/openapi-ts";

const args = process.argv.slice(2);
const host = args[0] || "localhost:8101";

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
      name: "@hey-api/client-axios",
      baseUrl: false,
    },
    {
      name: "@tanstack/react-query",
    },
    {
      name: "@hey-api/transformers",
      dates: true,
    },
    {
      name: "@hey-api/sdk",
      asClass: true,
      transformer: true,
    },
    {
      name: "@hey-api/typescript",
      enums: "javascript",
      readOnlyWriteOnlyBehavior: "off",
    },
  ],
});
