import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

// Region별 Noto Serif — 한자별 정확한 글자 모양
import "@fontsource/noto-serif-kr/korean-400.css";
import "@fontsource/noto-serif-kr/korean-600.css";
import "@fontsource/noto-serif-sc/chinese-simplified-400.css";
import "@fontsource/noto-serif-tc/chinese-traditional-400.css";

import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
