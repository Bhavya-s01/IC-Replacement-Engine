// src/tokens.ts — Dell Design System color tokens

export const DELL = {
  // Primary
  blue: '#0076CE',          // Dell Blue - primary brand color [1]

  // Neutrals [1]
  black: '#000000',
  cosmos: '#1D2C3B',        // Slate 700
  raven: '#40586D',         // Slate 500
  mist: '#C5D4E3',          // Slate 200
  white: '#FFFFFF',
  quartz: '#F0F0F0',        // Gray 200
  titanium: '#D2D2D2',      // Gray 400
  steel: '#B6B6B6',         // Gray 500

  // Blues [1]
  ocean: '#00468B',          // Blue 800
  midnight: '#0D2155',       // Deep blue - allowed for text [1]

  // Greens [1]
  forest: '#0B7C84',         // Teal 800
  teal: '#044E52',           // Teal 900

  // Purples [1]
  plum: '#66278F',           // Purple 800
  dusk: '#40155C',           // Purple 900

  // Semantic
  success: '#16A34A',
  warning: '#CA8A04',
  danger: '#DC2626',
}

// Typography: Roboto for customer-facing [1]
export const FONT = {
  primary: '"Roboto", "Arial", sans-serif',
  mono: '"Roboto Mono", "Consolas", monospace',
}

// Approved text colors on neutral backgrounds [1]:
// Dell Blue, Black, Cosmos, Midnight, White, Quartz
// On color backgrounds: White and Quartz only