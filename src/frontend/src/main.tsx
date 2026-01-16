import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { patchFirebaseEmulatorRequests } from "./lib/firebase-emulator";

patchFirebaseEmulatorRequests();

import("./App.tsx").then(({ default: App }) => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
});
