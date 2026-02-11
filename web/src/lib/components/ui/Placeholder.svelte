<script lang="ts">
  import { _ } from '$lib/i18n';
  
  interface Props {
    title?: string;
    description?: string;
    icon?: string;
  }
  
  let { 
    title = $_('page.developing'), 
    description = $_('page.developing.desc'),
    icon = 'ti-tool'
  }: Props = $props();
</script>

<div class="placeholder">
  <div class="content">
    <div class="icon-wrapper">
      <i class="ti {icon}"></i>
    </div>
    <h2>{title}</h2>
    <p>{description}</p>
  </div>
</div>

<style>
  .placeholder {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 400px;
  }
  
  .content {
    text-align: center;
    padding: 40px;
  }
  
  .icon-wrapper {
    width: 80px;
    height: 80px;
    margin: 0 auto 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 20px;
    background: var(--panel-elevated);
    border: 1px solid var(--line);
  }
  
  .icon-wrapper i {
    font-size: 40px;
    color: var(--accent);
  }
  
  h2 {
    font-size: 24px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 12px;
  }
  
  p {
    font-size: 14px;
    color: var(--text-muted);
    max-width: 300px;
    margin: 0 auto;
  }
</style>
