module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  // NEW: added with ET-12-FE(Jen)
  safelist: [
    'sm:w-11/12',
    'md:w-4/5',
    'lg:w-1/2',
    'xl:w-5/12',
    'max-h-[65vh]',
    'max-h-[90vh]',
    'overflow-hidden',
    // Status chips
    'bg-sky-100',
    'text-sky-700',
    'bg-emerald-100',
    'text-emerald-700',
    'bg-rose-100',
    'text-rose-700',
    'bg-gray-100',
    'text-gray-700',
    'bg-amber-100',
    'text-amber-700',
  ],
  theme: {
    extend: {
      colors: {
        primary: "#0D9488", // Teal 600
        background: "#F7F7F4",
        slate: "#787771",
        title: "#26251E",
        success: "#27AE60",
        warning: "#F2994A",
        error: "#EB5757",
        'landing-blue': '#24608E',
        'landing-cta': '#0F62FE',
        'landing-light': '#EDF8FF',
      },
      fontFamily: {
        sans: ["Geist","Poppins","Inter", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        serif: ["Georgia", "Times New Roman", "serif"],
        'ibm-serif': ['"IBM Plex Serif"', "Georgia", "serif"],
        'ibm-sans': ['"IBM Plex Sans"', "Inter", "system-ui", "sans-serif"],
        mono: ["SF Mono", "Menlo", "monospace"],
      },
      boxShadow: {
        'landing-card': '0px 2px 10px rgba(0,0,0,0.5)',
        'landing-testimonial': '0px 4px 10px #24608E',
        'landing-soft': '0px 4px 4px rgba(0,0,0,0.25)',
      },
      lineHeight: {
        snug: "1.35",
        relaxed: "1.6",
      },
    },
  },
  plugins: [],
};
