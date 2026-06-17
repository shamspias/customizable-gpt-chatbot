import { createPinia } from "pinia";
import { createApp } from "vue";
import App from "./App.vue";
import "./style.css";

// Dev-only demo mode (?demo): stub the API with fixtures so the UI renders a populated
// workspace without a backend. Dead-stripped from production builds (import.meta.env.DEV).
if (import.meta.env.DEV && new URLSearchParams(location.search).has("demo")) {
  const mode = new URLSearchParams(location.search).get("demo") || "";
  const { installDemo } = await import("./demo");
  installDemo(mode);
}

createApp(App).use(createPinia()).mount("#app");
