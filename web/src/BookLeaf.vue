<script setup>
defineProps({
  title: String,
  chapter: String,
  text: String,
  visible: Number,
  part: Number,
  parts: Number,
})
</script>

<template>
  <div class="leaf">
    <div class="binding" aria-hidden="true"><i v-for="mark in 4" :key="mark"></i></div>
    <div class="leaf-frame">
      <div class="leaf-inscription" lang="zh-Hant" aria-hidden="true">
        <span class="fish"></span>
        <strong>{{ title }}</strong>
        <span class="leaf-chapter">{{ chapter }}</span>
        <span v-if="parts > 1" class="leaf-part">{{ part }}／{{ parts }}</span>
        <span class="fish fish-bottom"></span>
      </div>
      <div class="vertical-text" lang="zh-Hant" :aria-label="text" role="group">
        <span v-for="(glyph, index) in Array.from(text)" :key="index" aria-hidden="true"
          :class="{ concealed: index >= visible }">{{ glyph }}</span>
      </div>
      <span class="seal" aria-hidden="true">典藏</span>
    </div>
  </div>
</template>
