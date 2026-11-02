import os
import base64
import re
import requests
from dotenv import load_dotenv
from flask import Flask, render_template_string, request, jsonify

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()

PAGE = r"""
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ثبت تصویر</title>
<style>
*{box-sizing:border-box} body{margin:0;min-height:100vh;display:grid;place-items:center;
background:radial-gradient(circle at top,#263b68,#0b1020 65%);font-family:Tahoma,Arial;color:#f7f8ff;padding:22px}
.card{width:min(100%,440px);background:#ffffff12;border:1px solid #ffffff25;backdrop-filter:blur(18px);
border-radius:26px;padding:25px;box-shadow:0 22px 70px #0008}
.badge{display:inline-block;padding:7px 12px;border-radius:30px;background:#8b5cf633;color:#c4b5fd;font-size:12px}
h1{font-size:24px;margin:16px 0 8px} p{color:#c6cbe0;line-height:1.9;font-size:14px}
video{width:100%;aspect-ratio:4/3;object-fit:cover;background:#080b14;border-radius:18px;margin-top:12px}
.actions{display:grid;gap:10px;margin-top:16px}
button{border:0;border-radius:14px;padding:14px;font-weight:bold;font-size:15px;cursor:pointer}
.primary{background:linear-gradient(90deg,#8b5cf6,#4f8cff);color:white}
.secondary{background:#ffffff18;color:white;border:1px solid #ffffff25}
button:disabled{opacity:.45;cursor:not-allowed}
.note{font-size:12px;color:#aeb6d0;margin-top:14px}
#status{min-height:24px;font-size:13px;color:#d9d5ff;margin-top:12px}
</style>
</head>
<body>
<main class="card">
 <span class="badge">ثبت تصویر با رضایت شما</span>
 <h1>آماده ثبت عکس هستید؟</h1>
 <p>برای ادامه، ابتدا اجازه دسترسی به دوربین را بدهید. هیچ عکسی بدون فشردن دکمه «ثبت و ارسال عکس» گرفته یا ارسال نمی‌شود.</p>
 <video id="preview" autoplay playsinline muted></video>
 <div class="actions">
  <button class="primary" id="start">فعال‌سازی دوربین</button>
  <button class="secondary" id="capture" disabled>ثبت و ارسال عکس</button>
 </div>
 <div id="status" role="status"></div>
 <p class="note">با انتخاب دکمه ثبت و ارسال، تصویر شما به مدیر این صفحه در تلگرام ارسال می‌شود.</p>
</main>
<canvas id="canvas" hidden></canvas>
<script>
const video=document.getElementById('preview');
const start=document.getElementById('start');
const capture=document.getElementById('capture');
const statusBox=document.getElementById('status');
let stream=null;

start.addEventListener('click', async()=>{
  try{
    stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:"user"},audio:false});
    video.srcObject=stream;
    capture.disabled=false;
    start.textContent="دوربین فعال است";
    statusBox.textContent="پیش‌نمایش دوربین فعال شد. برای ارسال، دکمه ثبت عکس را بزنید.";
  }catch(e){
    statusBox.textContent="دسترسی به دوربین داده نشد یا دوربین در دسترس نیست.";
  }
});

capture.addEventListener('click', async()=>{
  if(!stream) return;
  capture.disabled=true;
  statusBox.textContent="در حال ارسال تصویر…";
  const canvas=document.getElementById('canvas');
  canvas.width=video.videoWidth; canvas.height=video.videoHeight;
  canvas.getContext('2d').drawImage(video,0,0);
  const image=canvas.toDataURL('image/jpeg',0.88);
  try{
    const res=await fetch('/send-photo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image})});
    const data=await res.json();
    if(!res.ok) throw new Error(data.error||'ارسال ناموفق بود');
    statusBox.textContent="عکس با موفقیت ارسال شد. ممنون!";
    stream.getTracks().forEach(t=>t.stop());
    video.srcObject=null;
    start.disabled=true;
  }catch(e){
    statusBox.textContent=e.message||"خطا در ارسال عکس.";
    capture.disabled=false;
  }
});
</script>
</body>
</html>
"""

@app.get("/")
def home():
    return render_template_string(PAGE)

@app.post("/send-photo")
def send_photo():
    if not BOT_TOKEN or not CHAT_ID:
        return jsonify(error="تنظیمات ربات تلگرام در سرور کامل نشده است."), 500
    payload = request.get_json(silent=True) or {}
    data_url = payload.get("image", "")
    match = re.fullmatch(r"data:image/jpeg;base64,([A-Za-z0-9+/=]+)", data_url)
    if not match:
        return jsonify(error="فایل تصویر معتبر نیست."), 400
    try:
        photo = base64.b64decode(match.group(1), validate=True)
        if len(photo) > 6 * 1024 * 1024:
            return jsonify(error="حجم عکس بیش از حد مجاز است."), 413
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        response = requests.post(
            url,
            data={"chat_id": CHAT_ID, "caption": "تصویر ثبت‌شده با رضایت کاربر"},
            files={"photo": ("capture.jpg", photo, "image/jpeg")},
            timeout=25,
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            return jsonify(error="تلگرام تصویر را نپذیرفت."), 502
        return jsonify(ok=True)
    except Exception:
        app.logger.exception("Photo delivery failed")
        return jsonify(error="ارسال تصویر انجام نشد. تنظیمات ربات و اتصال سرور را بررسی کنید."), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
