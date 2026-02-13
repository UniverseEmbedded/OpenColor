<script lang="ts">
  import { _ } from '$lib/i18n';

  // Props
  interface Props {
    isOpen: boolean;
    onClose: () => void;
  }
  let { isOpen, onClose }: Props = $props();

  // 彩蛋动画状态
  let isEasterEgg = $state(false);

  // 触发彩蛋动画
  function triggerEasterEgg() {
    if (isEasterEgg) return;
    isEasterEgg = true;
    // 动画时长约 3.5s，之后恢复
    setTimeout(() => {
      isEasterEgg = false;
    }, 3500);
  }

  // 点击背景关闭
  function handleBackdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) {
      onClose();
    }
  }

  function handleBackdropKeydown(event: KeyboardEvent) {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }
    if (event.target === event.currentTarget) {
      event.preventDefault();
      onClose();
    }
  }

  // ESC键关闭
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      onClose();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if isOpen}
  <div
    class="modal"
    class:show={isOpen}
    role="dialog"
    aria-modal="true"
    aria-labelledby="aboutTitle"
    onclick={handleBackdropClick}
    onkeydown={handleBackdropKeydown}
    tabindex="0"
  >
    <div class="box" style="width:min(480px, 92vw)">
      <div class="hd">
        <!-- 模态框标题 -->
        <b id="aboutTitle"><i class="ti ti-alert-circle"></i> {$_('modal.aboutTitle')}</b>
        <!-- 关闭按钮 -->
        <button class="btn" onclick={onClose}>
          <i class="ti ti-x"></i>{$_('app.close')}
        </button>
      </div>
      <div class="bd" style="text-align:center; padding:30px 20px">
        <div class="logo-big">
          <button class="logo-btn" type="button" onclick={triggerEasterEgg} aria-label="触发彩蛋">
            <img
              src="/icon.svg"
              alt="OpenColor Logo"
              class:easter-egg={isEasterEgg}
            />
          </button>
        </div>
        <!-- 应用名称 -->
        <h2 style="margin:0 0 10px; font-size:24px">{$_('app.name')}</h2>
        <!-- 应用描述 -->
        <p style="color:var(--text-muted); font-size:14px; line-height:1.6; margin-bottom:24px">
          {$_('modal.aboutDesc')}
        </p>
        <div class="hr"></div>
        <!-- GitHub 链接 -->
        <div style="margin:20px 0">
          <a
            href="https://github.com/UniverseEmbedded/OpenColor"
            target="_blank"
            rel="noopener noreferrer"
            style="color:var(--accent); text-decoration:none; display:flex; align-items:center; justify-content:center; gap:8px; font-size:14px"
          >
            <i class="ti ti-brand-github" style="font-size:20px"></i>
            {$_('modal.aboutGithub')}
          </a>
        </div>
        <!-- 版本信息 -->
        <div class="muted" style="font-size:12px; margin-top:30px">
          {$_('modal.aboutVersion')}
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  /* 模态框样式 */
  .modal {
    position: fixed;
    inset: 0;
    display: none;
    align-items: center;
    justify-content: center;
    background: var(--overlay-bg, rgba(0, 0, 0, 0.6));
    padding: 18px;
    z-index: 1000;
    backdrop-filter: blur(4px);
  }

  .modal.show {
    display: flex;
  }

  .box {
    border-radius: 18px;
    border: 1px solid var(--line);
    background: var(--panel);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
    overflow: hidden;
  }

  .hd {
    padding: 12px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--line);
  }

  .hd b {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
  }

  .hd .btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 10px;
    background: transparent;
    border: 1px solid var(--line);
    border-radius: 6px;
    color: var(--text);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .hd .btn:hover {
    background: var(--panel-elevated);
    border-color: var(--accent);
  }

  .bd {
    padding: 14px;
  }

  .hr {
    height: 1px;
    background: var(--line);
    margin: 20px 0;
  }

  .muted {
    color: var(--text-muted);
  }

  /* 大 Logo 样式 */
  .logo-big {
    margin: 0 auto 24px;
    width: 96px;
    height: 96px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    filter: drop-shadow(0 12px 30px rgba(0, 0, 0, 0.3));
  }

  .logo-btn {
    width: 100%;
    height: 100%;
    padding: 0;
    border: none;
    background: transparent;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .logo-big:hover {
    transform: scale(1.08) rotate(2deg);
  }

  .logo-big img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    transition: opacity 0.5s ease;
  }

  /* 彩蛋动画样式 */
  .logo-big img.easter-egg {
    position: fixed;
    top: 50%;
    left: 50%;
    width: 96px;
    height: 96px;
    margin-top: -48px;
    margin-left: -48px;
    z-index: 9999;
    pointer-events: none;
    transform-origin: center;
    animation: easter-egg-anim 3.5s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  }

  /* 彩蛋动画关键帧 */
  @keyframes easter-egg-anim {
    0% {
      transform: scale(1) rotate(0deg);
      opacity: 1;
    }
    60% {
      transform: scale(150) rotate(1080deg);
      opacity: 1;
    }
    85% {
      transform: scale(150) rotate(1080deg);
      opacity: 0;
    }
    100% {
      transform: scale(1) rotate(0deg);
      opacity: 0;
    }
  }
</style>
