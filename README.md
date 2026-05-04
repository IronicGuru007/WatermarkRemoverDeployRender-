# Watermark Remover — Web Deploy

## Deploy to Render.com (FREE, no credit card)

### Step 1 — GitHub pe push karo
```bash
git init
git add .
git commit -m "watermark remover deploy"
git remote add origin https://github.com/YOURUSERNAME/watermark-remover.git
git push -u origin main
```

### Step 2 — Render pe deploy
1. https://render.com pe jaao → Sign up (GitHub se)
2. **New** → **Web Service** → apna GitHub repo select karo
3. Settings:
   - **Environment**: Python
   - **Build Command**: `apt-get update && apt-get install -y ffmpeg && pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 600 --workers 2`
4. **Create Web Service** → Deploy hoga (3-5 min)
5. Done! URL milega: `https://watermark-remover-xxxx.onrender.com`

---

## Local run (Termux/PC)
```bash
pip install flask gunicorn
# FFmpeg install karo pehle
python app.py
# http://localhost:5000
```

## Notes
- Max file size: 200 MB
- Files auto-delete after 1 hour
- Mobile touch drawing supported
