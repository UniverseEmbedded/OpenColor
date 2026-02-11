import "./app.css";
import { mount } from "svelte";
import Layout from "./routes/+layout.svelte";

// 使用Svelte 5的mount函数挂载组件
const app = mount(Layout, {
  target: document.getElementById("app")!,
});

export default app;
