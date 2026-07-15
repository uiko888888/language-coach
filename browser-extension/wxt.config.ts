import { defineConfig } from "wxt"

export default defineConfig({
  manifestVersion: 3,
  manifest: {
    name: "Language Coach Browser Bridge",
    description: "Extract, translate, and save webpage language to Language Coach.",
    permissions: ["storage", "contextMenus"],
    host_permissions: ["http://127.0.0.1/*", "http://localhost/*"],
    action: { default_title: "Language Coach" },
  },
})
