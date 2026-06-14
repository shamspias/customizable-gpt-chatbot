<script setup lang="ts">
// Faust's mascot — a clean, friendly squircle character. Tasteful and minimal
// (Google-simple), with a subtle blink/talk animation for a little personality.
withDefaults(defineProps<{ size?: number; talking?: boolean }>(), { size: 28, talking: false });
</script>

<template>
  <svg class="faust" :class="{ talking }" :width="size" :height="size" viewBox="0 0 40 40"
       fill="none" aria-hidden="true">
    <!-- head -->
    <rect x="4" y="5" width="32" height="32" rx="11" fill="currentColor" />
    <!-- little antenna -->
    <circle cx="20" cy="3.5" r="2" fill="currentColor" />
    <line x1="20" y1="5" x2="20" y2="7" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
    <!-- face -->
    <g class="eyes" fill="#fff">
      <circle cx="14.5" cy="19" r="3" />
      <circle cx="25.5" cy="19" r="3" />
    </g>
    <!-- cheeks -->
    <circle cx="11" cy="25" r="1.6" fill="#fff" opacity="0.35" />
    <circle cx="29" cy="25" r="1.6" fill="#fff" opacity="0.35" />
    <!-- smile -->
    <path class="mouth" d="M15 26 Q20 30 25 26" stroke="#fff" stroke-width="2"
          stroke-linecap="round" fill="none" />
  </svg>
</template>

<style scoped>
.faust { color: var(--accent); display: block; }
.faust .eyes { transform-origin: center; animation: faust-blink 5s infinite; }
@keyframes faust-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.15); }
}
.faust.talking .mouth { animation: faust-talk 0.5s ease-in-out infinite; transform-origin: 20px 27px; }
@keyframes faust-talk { 0%, 100% { transform: scaleY(1); } 50% { transform: scaleY(0.55); } }
@media (prefers-reduced-motion: reduce) {
  .faust .eyes, .faust.talking .mouth { animation: none; }
}
</style>
