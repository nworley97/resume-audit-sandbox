module.exports = {
  content: [
    "./templates/**/*.html",
    "./**/*.html",           // catch-all for templates
    "./static/**/*.js",
    "./app.py",              // include Python files in case classes are inline
  ],
  theme: {
    extend: {
      colors: {
        slate: "#475569",
        "title-black": "#0F172A",
        "blue-600": "#155CFA",
        background: "#F9FBFD",
        primary: "#08C5FF",
        title: "#1A1C1F",
        success: "#27AE60",
        warning: "#F2994A",
        error: "#EB5757",
        "apple-blue": "#007AFF",
      },
    },
  },
  plugins: [],
}
