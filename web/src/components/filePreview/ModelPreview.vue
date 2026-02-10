<template>
  <div class="model-preview">
    <div class="model-frame">
      <div class="model-canvas" ref="modelContainer"></div>
      <div v-if="loading || errorText" class="model-overlay">
        <i :class="loading ? 'ti ti-loader-2 ti-spin' : 'ti ti-alert-circle'"></i>
        <span>{{ loading ? (loadingText || '加载中...') : (errorText || '加载失败') }}</span>
      </div>
    </div>
    <div class="model-info" v-if="modelInfo">
      <div class="info-row">
        <span class="label">格式:</span>
        <span class="value">{{ modelInfo.format }}</span>
      </div>
      <div class="info-row">
        <span class="label">大小:</span>
        <span class="value">{{ modelInfo.size }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, nextTick, watch } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { ThreeMFLoader } from 'three/examples/jsm/loaders/3MFLoader.js';

const props = defineProps({
  filePath: {
    type: String,
    default: ''
  },
  fileName: {
    type: String,
    default: ''
  },
  fileData: {
    type: ArrayBuffer,
    default: null
  },
  modelInfo: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  },
  loadingText: {
    type: String,
    default: ''
  },
  errorText: {
    type: String,
    default: ''
  }
});

const modelContainer = ref(null);
let modelRenderer = null;
let modelScene = null;
let modelCamera = null;
let modelControls = null;
let modelResizeObserver = null;
let modelRaf = 0;

const base64ToUint8Array = (b64) => {
  const binary = atob(String(b64 || ''));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
};

const dispose3DModel = () => {
  if (modelResizeObserver) {
    try {
      modelResizeObserver.disconnect();
    } catch (e) {
      console.error('[3D预览] 释放 ResizeObserver 失败:', e);
    }
    modelResizeObserver = null;
  }
  if (modelRaf) {
    cancelAnimationFrame(modelRaf);
    modelRaf = 0;
  }
  if (modelControls) {
    try {
      modelControls.dispose();
    } catch (e) {
      console.error('[3D预览] 释放 OrbitControls 失败:', e);
    }
    modelControls = null;
  }
  if (modelScene) {
    try {
      modelScene.traverse((obj) => {
        const mesh = obj;
        if (mesh.geometry && typeof mesh.geometry.dispose === 'function') {
          mesh.geometry.dispose();
        }
        const mat = mesh.material;
        if (Array.isArray(mat)) {
          mat.forEach((m) => m && typeof m.dispose === 'function' && m.dispose());
        } else if (mat && typeof mat.dispose === 'function') {
          mat.dispose();
        }
      });
    } catch (e) {
      console.error('[3D预览] 释放场景资源失败:', e);
    }
    modelScene = null;
  }
  if (modelRenderer) {
    try {
      modelRenderer.dispose();
      if (modelRenderer.domElement && modelRenderer.domElement.parentNode) {
        modelRenderer.domElement.parentNode.removeChild(modelRenderer.domElement);
      }
    } catch (e) {
      console.error('[3D预览] 释放渲染器失败:', e);
    }
    modelRenderer = null;
  }
  modelCamera = null;
};

const init3DModel = () => {
  const el = modelContainer.value;
  if (!el) return false;

  const w = Math.max(1, el.clientWidth || 1);
  const h = Math.max(1, el.clientHeight || 1);

  modelRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  modelRenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  modelRenderer.setSize(w, h, false);
  modelRenderer.outputColorSpace = THREE.SRGBColorSpace;
  el.innerHTML = '';
  el.appendChild(modelRenderer.domElement);

  modelScene = new THREE.Scene();
  modelScene.add(new THREE.AmbientLight(0xffffff, 0.75));
  const dir = new THREE.DirectionalLight(0xffffff, 0.9);
  dir.position.set(1.5, 2.0, 2.0);
  modelScene.add(dir);

  modelCamera = new THREE.PerspectiveCamera(45, w / h, 0.01, 100000);
  modelCamera.position.set(2, 2, 2);

  modelControls = new OrbitControls(modelCamera, modelRenderer.domElement);
  modelControls.enableDamping = true;
  modelControls.dampingFactor = 0.08;
  modelControls.target.set(0, 0, 0);
  modelControls.update();

  modelResizeObserver = new ResizeObserver(() => {
    if (!modelRenderer || !modelCamera || !modelContainer.value) return;
    const w2 = Math.max(1, modelContainer.value.clientWidth || 1);
    const h2 = Math.max(1, modelContainer.value.clientHeight || 1);
    modelRenderer.setSize(w2, h2, false);
    modelCamera.aspect = w2 / h2;
    modelCamera.updateProjectionMatrix();
  });
  modelResizeObserver.observe(el);

  const tick = () => {
    if (!modelRenderer || !modelScene || !modelCamera) return;
    if (modelControls) modelControls.update();
    modelRenderer.render(modelScene, modelCamera);
    modelRaf = requestAnimationFrame(tick);
  };
  tick();
  return true;
};

const fitCameraToObject = (obj) => {
  if (!modelCamera || !modelControls) return;
  const box = new THREE.Box3().setFromObject(obj);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());

  const maxSize = Math.max(size.x, size.y, size.z) || 1;
  const dist = maxSize * 2.2;

  modelCamera.near = Math.max(0.01, dist / 1000);
  modelCamera.far = dist * 1000;
  modelCamera.updateProjectionMatrix();

  modelCamera.position.set(center.x + dist, center.y + dist, center.z + dist);
  modelControls.target.copy(center);
  modelControls.update();
};

const load3DModel = async (buffer) => {
  if (!buffer) return;

  dispose3DModel();

  if (!init3DModel()) {
    console.error('[3D预览] 无法初始化 3D 预览容器');
    return;
  }

  try {
    const name = props.fileName || '';
    const ext = name.split('.').pop()?.toLowerCase() || '';

    let rootObj = null;
    if (ext === 'stl') {
      const loader = new STLLoader();
      const geom = loader.parse(buffer);
      geom.computeVertexNormals();
      const mat = new THREE.MeshStandardMaterial({ color: 0xbcc6d4, metalness: 0.05, roughness: 0.75 });
      const mesh = new THREE.Mesh(geom, mat);
      rootObj = mesh;
    } else if (ext === '3mf') {
      const loader = new ThreeMFLoader();
      const group = loader.parse(buffer);
      group.traverse((obj) => {
        if (obj.isMesh && obj.material) {
          const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
          mats.forEach((m) => {
            if (!m) return;
            m.side = THREE.DoubleSide;
            m.transparent = true;
            if (typeof m.opacity === 'number' && m.opacity <= 0) m.opacity = 1;
            if (!m.color) m.color = new THREE.Color(0xbcc6d4);
          });
        }
      });
      rootObj = group;
    } else {
      console.warn('[3D预览] 暂不支持的模型格式:', ext, name);
      return;
    }

    modelScene.add(rootObj);
    fitCameraToObject(rootObj);
  } catch (e) {
    console.error('[3D预览] 加载模型失败:', e);
  }
};

watch(() => props.fileData, async (newData) => {
  if (newData) {
    await nextTick();
    load3DModel(newData);
  }
}, { immediate: true });

onBeforeUnmount(() => {
  dispose3DModel();
});
</script>

<style scoped>
.model-preview {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 300px;
  gap: 12px;
}

.model-frame {
  position: relative;
  width: 100%;
}

.model-canvas {
  width: 100%;
  height: min(460px, 55vh);
  background: var(--bg-alpha);
  border-radius: 12px;
  overflow: hidden;
}

.model-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--muted);
  background: rgba(0, 0, 0, 0.15);
  border-radius: 12px;
  pointer-events: none;
}

.model-info {
  margin-top: 20px;
  text-align: left;
  display: inline-block;
}

.info-row {
  display: flex;
  gap: 12px;
  margin: 8px 0;
  font-size: 14px;
}

.info-row .label {
  color: var(--muted);
  min-width: 80px;
}

.info-row .value {
  color: var(--text);
  font-weight: 500;
}
</style>
