# resume-audit-sandbox

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm

### Setup Steps

1. **Clone and install dependencies**
```bash
git clone <repository-url>
cd resume-audit-sandbox

# Install Python dependencies
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Install Node.js dependencies
npm install
```

2. **Build CSS (IMPORTANT!)**
```bash
npm run build:css
```

3. **Run the application**
```bash
# Terminal 1: Main Flask app
python app.py

# Terminal 2: Analytics service
python analytics_service.py

# Terminal 3: Next.js dashboard (optional)
cd analytics_ui/dashboard
npm install
npm run dev
```

### 🔧 CSS Build Issues

If you encounter CSS issues after cloning:

1. **Clean and rebuild**
```bash
rm -rf node_modules package-lock.json
npm install
npm run build:css
```

2. **Check Tailwind version**
```bash
npx tailwindcss --version
```

3. **Manual build**
```bash
npx tailwindcss -i ./static/css/app.css -o ./static/css/output.css --minify
```

### 📁 Project Structure
- `static/css/app.css` - Tailwind source file
- `static/css/output.css` - Built CSS (generated)
- `tailwind.config.js` - Tailwind configuration
- `postcss.config.js` - PostCSS configuration