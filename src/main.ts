import { startApp } from "./app";
import "./styles.css";

const root = document.getElementById("app");
if (!root) throw new Error("#app missing");
void startApp(root);
