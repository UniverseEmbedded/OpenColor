<template>
  <div>
    <div class="hint" style="display:flex; align-items:center; justify-content:space-between">
      <span><i class="ti ti-bulb"></i> {{ t("hint.quickCalib") }}</span>
      <div class="row" style="gap:8px">
        <button class="btn sm primary" @click="$emit('genQuickCalibStl')">
          <i class="ti ti-file-download"></i> {{ t("btn.genQuickCalibStl") }}
        </button>
        <button class="btn sm primary" @click="$emit('showScreenCalibrator')">
          <i class="ti ti-screen-share"></i> 屏幕校准工具
        </button>
      </div>
    </div>
    <div class="hr"></div>
    <div class="list">
      <div class="item">
        <div class="top">
          <div class="left"><span class="dot" style="background:rgba(255,80,80,.85)"></span><b>{{ t("label.chanR") }}</b><span class="muted">{{ t("label.matRed") }}</span></div>
          <button class="btn" @click="$emit('importPhoto')"><i class="ti ti-photo-plus"></i>{{ t("btn.importPhoto") }}</button>
        </div>
        <div class="sub">{{ t("hint.photoAdvice") }}</div>
      </div>
      <div class="item">
        <div class="top">
          <div class="left"><span class="dot" style="background:rgba(100,255,140,.85)"></span><b>{{ t("label.chanG") }}</b><span class="muted">{{ t("label.matGreen") }}</span></div>
          <button class="btn" @click="$emit('importPhoto')"><i class="ti ti-photo-plus"></i>{{ t("btn.importPhoto") }}</button>
        </div>
        <div class="sub">{{ t("hint.isoAdvice") }}</div>
      </div>
      <div class="item">
        <div class="top">
          <div class="left"><span class="dot" style="background:rgba(90,160,255,.90)"></span><b>{{ t("label.chanB") }}</b><span class="muted">{{ t("label.matBlue") }}</span></div>
          <button class="btn" @click="$emit('importPhoto')"><i class="ti ti-photo-plus"></i>{{ t("btn.importPhoto") }}</button>
        </div>
        <div class="sub">{{ t("hint.v1Stable") }}</div>
      </div>
      <div class="item">
        <div class="top">
          <div class="left"><span class="dot" style="background:rgba(245,245,245,.92)"></span><b>{{ t("label.chanW") }}</b><span class="muted">{{ t("label.matWhite") }}</span></div>
          <button class="btn" @click="$emit('importPhoto')"><i class="ti ti-photo-plus"></i>{{ t("btn.importPhoto") }}</button>
        </div>
        <div class="sub">{{ t("hint.profileSaveHint") }}</div>
      </div>
    </div>
    <div class="hr"></div>
    <div class="row">
      <button class="btn primary" @click="$emit('genProfile')"><i class="ti ti-checklist"></i>{{ t("btn.genProfile") }}</button>
      <button class="btn" @click="$emit('saveProfile')"><i class="ti ti-device-floppy"></i>{{ t("btn.save") }}</button>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";

const { t } = useI18n();

defineEmits([
  'genQuickCalibStl',
  'showScreenCalibrator',
  'importPhoto',
  'genProfile',
  'saveProfile'
]);
</script>

<style scoped>
.hint {
  background: var(--bg-alpha);
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 13px;
  color: var(--muted);
}

.hint i {
  margin-right: 6px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.item {
  background: var(--bg-alpha);
  border-radius: 12px;
  padding: 16px;
}

.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}

.sub {
  font-size: 12px;
  color: var(--muted);
  padding-left: 24px;
}

.row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.hr {
  height: 1px;
  background: var(--hr-color);
  margin: 16px 0;
}
</style>
