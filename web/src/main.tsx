import React from "react";
import { createRoot } from "react-dom/client";
import "@carbon/styles/css/styles.css";
import "./style.scss";
import App from "./ui";
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
