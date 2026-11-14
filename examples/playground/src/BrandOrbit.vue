<template>
  <svg viewBox="0 0 640 640" class="brand-orbit" aria-hidden="true">
    <defs>
      <radialGradient id="orb-surface" cx="30%" cy="23%" r="82%"><stop stop-color="#f2c9fa"/><stop offset=".37" stop-color="#c394e4"/><stop offset=".73" stop-color="#8052ae"/><stop offset="1" stop-color="#3b234f"/></radialGradient>
      <linearGradient id="orb-rim" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff8e9"/><stop offset=".5" stop-color="#dca4ef"/><stop offset="1" stop-color="#70507c"/></linearGradient>
      <linearGradient id="orb-line" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#8c609e" stop-opacity="0"/><stop offset=".3" stop-color="#c5a3c7"/><stop offset=".65" stop-color="#61446e"/><stop offset="1" stop-color="#d8bccb" stop-opacity="0"/></linearGradient>
      <mask id="orb-cut"><circle cx="320" cy="320" r="202" fill="white"/><path d="M320 211C336 280 360 304 429 320C360 336 336 360 320 429C304 360 280 336 211 320C280 304 304 280 320 211Z" fill="black"/></mask>
      <filter id="orb-shadow"><feGaussianBlur stdDeviation="16"/></filter>
    </defs>
    <ellipse cx="329" cy="555" rx="156" ry="15" fill="#604773" opacity=".13" filter="url(#orb-shadow)"/>
    <g class="orb-shell">
      <circle cx="320" cy="320" r="202" fill="url(#orb-surface)" mask="url(#orb-cut)"/>
      <circle cx="320" cy="320" r="202" fill="none" stroke="url(#orb-rim)" stroke-width="1.4"/>
      <path d="M320 211C336 280 360 304 429 320C360 336 336 360 320 429C304 360 280 336 211 320C280 304 304 280 320 211Z" fill="none" stroke="url(#orb-rim)" stroke-width="1.3"/>
      <ellipse v-for="i in 15" :key="i" cx="320" cy="320" :rx="202 - i * 4" :ry="44 + i * 9" transform="rotate(-31 320 320)" fill="none" stroke="#f1d4ec" :stroke-opacity=".04 + i * .004" stroke-width=".7" mask="url(#orb-cut)"/>
    </g>
    <ellipse cx="320" cy="320" rx="287" ry="91" transform="rotate(-31 320 320)" fill="none" stroke="url(#orb-line)" stroke-width="1.25"/>
    <ellipse cx="320" cy="320" rx="279" ry="102" transform="rotate(-31 320 320)" fill="none" stroke="#aa87b3" stroke-opacity=".2" stroke-width=".6"/>
    <circle cx="79" cy="468" r="5" fill="#a86bb4"/><circle cx="553" cy="184" r="3" fill="#9b71a5"/>
    <path d="M506 87h17m-8.5-8.5v17M113 177h11m-5.5-5.5v11" stroke="#b696b5" stroke-width="1"/>
    <text x="471" y="551" fill="#9d7fa2" font-family="monospace" font-size="8" letter-spacing="2">FIG. 01 / HUMAN SIGNAL</text>
  </svg>
</template>
