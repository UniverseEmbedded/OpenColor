// Vue 模块声明
declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<{}, {}, any>;
  export default component;
}
// CSS 模块声明
declare module "*.css" {
  const content: string;
  export default content;
}
