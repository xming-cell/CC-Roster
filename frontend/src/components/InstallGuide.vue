<script setup lang="ts">
import { ref } from 'vue'

const open = ref(false)
</script>

<template>
  <div class="install-guide">
    <button
      type="button"
      class="install-guide__toggle"
      :aria-expanded="open"
      aria-controls="install-guide-content"
      @click="open = !open"
    >
      怎么装
    </button>

    <section
      v-if="open"
      id="install-guide-content"
      class="install-guide__content"
      aria-label="安装与配置指引"
    >
      <h3>Claude Code</h3>
      <p>
        安装：<code>npm install -g @anthropic-ai/claude-code</code>
      </p>
      <p>
        配置：编辑 <code>~/.claude/settings.json</code>（或 <code>CLAUDE_CONFIG_DIR</code>
        指向的目录）：
      </p>
      <pre><code>{
  "model": "claude-sonnet-4",
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
    "ANTHROPIC_AUTH_TOKEN": "你的密钥"
  }
}</code></pre>

      <h3>Codex CLI</h3>
      <p>
        安装：<code>npm install -g @openai/codex</code>
      </p>
      <p>
        配置：编辑 <code>~/.codex/config.toml</code>（或 <code>CODEX_HOME</code> 指向的目录）：
      </p>
      <pre><code>model = "gpt-5"
model_provider = "openai"</code></pre>
      <p>
        密钥放在同目录的 <code>auth.json</code>：
        <code>{"OPENAI_API_KEY": "你的密钥"}</code>。
      </p>

      <p class="install-guide__note">
        本应用只读取上述配置文件，不代装、不联网；安装命令与字段以各工具官方文档为准。
      </p>
    </section>
  </div>
</template>

<style scoped>
.install-guide {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-3);
}

.install-guide__toggle {
  border: 1px solid var(--friend-accent);
  border-radius: var(--radius-full);
  padding: var(--space-1) var(--space-3);
  background: var(--color-surface);
  color: var(--friend-accent);
  font-size: var(--font-size-sm);
  cursor: pointer;
}

.install-guide__toggle:hover {
  background: var(--friend-accent-soft);
}

.install-guide__toggle:focus-visible {
  outline: 2px solid var(--friend-accent);
  outline-offset: 2px;
}

.install-guide__content {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  background: var(--color-sidebar-bg);
}

.install-guide__content h3 {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-md);
}

.install-guide__content p {
  margin: 0;
  overflow-wrap: anywhere;
  font-size: var(--font-size-sm);
}

.install-guide__content pre {
  margin: 0;
  overflow-wrap: anywhere;
  border-radius: var(--radius-sm);
  padding: var(--space-3);
  background: var(--color-surface);
  font-size: var(--font-size-xs);
  white-space: pre-wrap;
}

.install-guide__content code {
  overflow-wrap: anywhere;
  font-family: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
}

.install-guide__content p.install-guide__note {
  color: var(--color-text-secondary);
}
</style>