import { useEffect, useState } from "react";
import App from "./ui";
import Landing from "./landing/Landing";

function isWorkbench() {
  return window.location.hash.startsWith("#/workbench");
}

export default function Root() {
  const [workbench, setWorkbench] = useState(isWorkbench);
  useEffect(() => {
    const update = () => setWorkbench(isWorkbench());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return workbench ? <App /> : <Landing />;
}
