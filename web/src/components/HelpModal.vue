<template>
  <div class="modal" :class="{ show: isOpen }" role="dialog" aria-modal="true" aria-labelledby="helpTitle" @click.self="emit('close')">
    <div class="box help-box">
      <div class="hd">
        <!-- 帮助模态框标题 -->
        <b id="helpTitle"><i class="ti ti-help-circle"></i> {{ t("modal.helpTitle") }}</b>
        <!-- 关闭按钮 -->
        <button class="btn" @click="emit('close')"><i class="ti ti-x"></i>{{ t("btn.close") }}</button>
      </div>
      <div class="bd">
        <div class="help-layout">
          <!-- 帮助导航 -->
          <div class="help-nav">
            <div class="help-nav-title">{{ t("modal.helpDocs") }} · {{ currentCategoryTitle }}</div>

            <div class="help-nav-list">
              <button
                v-for="doc in currentDocs"
                :key="doc.key"
                class="help-doc-btn"
                :class="{ active: helpDocKey === doc.key }"
                @click="helpDocKey = doc.key"
              >
                {{ doc.title }}
              </button>
            </div>

            <div class="help-nav-switch" role="tablist" :aria-label="t('modal.helpDocs')">
              <button
                class="help-switch-btn"
                :class="{ active: helpCategory === 'tutorials' }"
                role="tab"
                :aria-selected="helpCategory === 'tutorials'"
                @click="helpCategory = 'tutorials'"
              >
                <i class="ti ti-book"></i>
                {{ t('modal.helpTabTutorials') }}
              </button>
              <button
                class="help-switch-btn"
                :class="{ active: helpCategory === 'wiki' }"
                role="tab"
                :aria-selected="helpCategory === 'wiki'"
                @click="helpCategory = 'wiki'"
              >
                <i class="ti ti-notebook"></i>
                {{ t('modal.helpTabWiki') }}
              </button>
            </div>
          </div>
          <!-- 帮助内容（Markdown 渲染） -->
          <div class="help-content" v-html="helpDocHtml"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 导入 Vue 响应式 API
import { computed, ref, watch } from "vue";
// 导入国际化功能
import { useI18n } from "vue-i18n";
// 导入 Markdown 解析器
import MarkdownIt from "markdown-it";

// 获取国际化翻译函数和语言
const { t, locale } = useI18n();

// 定义组件属性
const props = defineProps({
  isOpen: Boolean // 是否打开
});

// 定义组件事件
const emit = defineEmits(['close']);

const tutorialDocsZhMod = import.meta.glob("../assets/docs/zh/tutorials/**/*.md", { eager: true, query: "?raw", import: "default" });
const wikiDocsZhMod = import.meta.glob("../assets/docs/zh/wiki/**/*.md", { eager: true, query: "?raw", import: "default" });
const tutorialDocsEnMod = import.meta.glob("../assets/docs/en/tutorials/**/*.md", { eager: true, query: "?raw", import: "default" });
const wikiDocsEnMod = import.meta.glob("../assets/docs/en/wiki/**/*.md", { eager: true, query: "?raw", import: "default" });

const extractMarkdownTitle = (markdown) => {
  if (!markdown) return "";
  const m = String(markdown).match(/^#\s+(.+?)\s*$/m);
  return m?.[1]?.trim() || "";
};

const prettifyFileBase = (base) => {
  return String(base || "")
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .trim();
};

const toDocList = (modules, preferredBaseNames) => {
  const prefMap = new Map();
  (preferredBaseNames || []).forEach((name, idx) => prefMap.set(String(name).toLowerCase(), idx));

  const docs = Object.entries(modules || {}).map(([path, raw]) => {
    const content = typeof raw === "string" ? raw : "";
    const fileName = String(path).split("/").pop() || String(path);
    const baseName = fileName.replace(/\.md$/i, "");
    const title = extractMarkdownTitle(content) || prettifyFileBase(baseName) || fileName;
    return {
      key: String(path),
      title,
      content,
      baseName,
    };
  });

  docs.sort((a, b) => {
    const aPref = prefMap.has(String(a.baseName).toLowerCase()) ? prefMap.get(String(a.baseName).toLowerCase()) : 9999;
    const bPref = prefMap.has(String(b.baseName).toLowerCase()) ? prefMap.get(String(b.baseName).toLowerCase()) : 9999;
    if (aPref !== bPref) return aPref - bPref;
    return String(a.title).localeCompare(String(b.title), "zh");
  });

  return docs;
};

const tutorialDocsZh = toDocList(tutorialDocsZhMod, ["start", "quick-start", "README"]);
const wikiDocsZh = toDocList(wikiDocsZhMod, ["README"]);
const tutorialDocsEn = toDocList(tutorialDocsEnMod, ["start", "README"]);
const wikiDocsEn = toDocList(wikiDocsEnMod, ["README"]);

const helpCategory = ref("tutorials");
const helpDocKey = ref("");

// Markdown 解析器实例
const helpMarkdown = new MarkdownIt({ breaks: true, linkify: true });

const isZh = computed(() => locale.value.toLowerCase().startsWith("zh"));

const currentDocs = computed(() => {
  const isZh = locale.value.toLowerCase().startsWith("zh");
  const src = isZh ? { tutorials: tutorialDocsZh, wiki: wikiDocsZh } : { tutorials: tutorialDocsEn, wiki: wikiDocsEn };
  return helpCategory.value === "wiki" ? src.wiki : src.tutorials;
});

const currentCategoryTitle = computed(() => {
  return helpCategory.value === "wiki" ? t("modal.helpTabWiki") : t("modal.helpTabTutorials");
});

const pickDefaultDocKey = (docs, category) => {
  const list = Array.isArray(docs) ? docs : [];
  if (!list.length) return "";

  const preferred = category === "wiki" ? ["README", "concepts", "faq"] : ["start", "quick-start", "README"];
  for (const base of preferred) {
    const found = list.find((d) => String(d.baseName).toLowerCase() === String(base).toLowerCase());
    if (found?.key) return found.key;
  }
  return list[0].key;
};

const syncDocKey = () => {
  const docs = currentDocs.value;
  const exists = Array.isArray(docs) && docs.some((d) => d.key === helpDocKey.value);
  if (!exists) helpDocKey.value = pickDefaultDocKey(docs, helpCategory.value);
};

watch([helpCategory, isZh], () => syncDocKey(), { immediate: true });

// 计算属性：当前帮助文档
const currentHelpDoc = computed(() => currentDocs.value.find((doc) => doc.key === helpDocKey.value) || currentDocs.value[0]);

// 计算属性：渲染的 HTML 内容
const helpDocHtml = computed(() => helpMarkdown.render(currentHelpDoc.value?.content || ""));

// 监听模态框打开状态
watch(() => props.isOpen, (isOpen) => {
  if (isOpen) {
    helpCategory.value = "tutorials";
    syncDocKey();
  }
});
</script>
