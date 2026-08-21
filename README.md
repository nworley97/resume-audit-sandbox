# resume-audit-sandbox

## Branch and deployment workflow

This repository has two long-lived branches:

- `main` is production. Merging or pushing it can deploy the production web/API service.
- `Dev` is the sandbox branch watched by Render. Its capital `D` is retained because the existing Render service is configured with that exact branch name.

Create short-lived feature branches from `Dev`, merge them back into `Dev` for sandbox verification, then open a `Dev` → `main` pull request for production. Delete the feature branch after the merge.

The sandbox and production services currently share one database. Sandbox testing can therefore change production data. Keep schema changes additive, use an Alembic migration, and never use destructive test data in the sandbox.

The iOS app is versioned in this repository but deployed separately through Xcode and TestFlight. See [`ios/README.md`](ios/README.md).

## 🚀 Quick Startt

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
