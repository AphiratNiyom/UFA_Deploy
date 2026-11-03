# 🌊 UFA Flood Alert & Prediction System (UFAsite)

ระบบเฝ้าระวัง แจ้งเตือน และทำนายระดับน้ำท่วมลุ่มน้ำมูล (สถานี M.7 เมืองอุบลราชธานี) แบบครบวงจร พัฒนาด้วย **Django 5**, เชื่อมต่อข้อมูลเรียลไทม์ผ่าน **ThaiWater API**, จัดเก็บข้อมูลบน **TiDB Serverless (MySQL-Compatible)**, ขับเคลื่อนด้วย **Hybrid Prediction System (AI 16 Features + Rule-based Anomaly Detection)**, พร้อมระบบ **LINE Chatbot** และหน้าบริหารจัดการ **Admin Panel**

---

## 📌 สารบัญ (Table of Contents)
1. [ฟีเจอร์เด่นของระบบ (Key Features)](#-ฟีเจอร์เด่นของระบบ-key-features)
2. [เทคโนโลยีและเครื่องมือ (Tech Stack)](#-เทคโนโลยีและเครื่องมือ-tech-stack)
3. [โครงสร้างโปรเจกต์ (Project Structure)](#-โครงสร้างโปรเจกต์-project-structure)
4. [เส้นทางและจุดเชื่อมต่อ (Endpoints)](#-เส้นทางและจุดเชื่อมต่อ-endpoints)
5. [การติดตั้งและเริ่มต้นใช้งาน (Quick Start)](#-การติดตั้งและเริ่มต้นใช้งาน-quick-start)
6. [คำสั่งระบบ (Management Commands)](#-คำสั่งระบบ-management-commands)
7. [สถาปัตยกรรมโมเดล AI และอุทกวิทยา (AI & Hydrology Architecture)](#-สถาปัตยกรรมโมเดล-ai-และอุทกวิทยา)
8. [ระบบบริหารจัดการ Admin Panel](#-ระบบบริหารจัดการ-admin-panel)
9. [การติดตั้งบนระบบ Production (Render Deployment)](#-การติดตั้งบนระบบ-production-render-deployment)
10. [ความปลอดภัยและการจัดการตัวแปรสภาพแวดล้อม (Security & Environment)](#-ความปลอดภัยและการจัดการตัวแปรสภาพแวดล้อม)

---

## 🚀 ฟีเจอร์เด่นของระบบ (Key Features)

- **📡 Real-time Water Monitoring:** ดึงข้อมูลระดับน้ำเรียลไทม์จาก **ThaiWater API (สสน. / กรมชลประทาน)** ครอบคลุม 3 สถานีหลักลุ่มน้ำมูล:
  - **TS2 (M.5):** สถานีต้นน้ำ อ.ราษีไศล จ.ศรีสะเกษ (ตรวจจับคลื่นน้ำหลากระยะไกล)
  - **TS16 (M.7):** สถานีวิกฤต สะพานเสรีประชาธิปไตย อ.เมือง จ.อุบลราชธานี (จุดทำนายหลัก)
  - **TS5 (M.11B):** สถานีท้ายน้ำ ท้ายแก่งสะพือ อ.พิบูลมังสาหาร จ.อุบลราชธานี (ตรวจจับภาวะน้ำหนุน)
- **🤖 Hybrid Prediction System (AI + Hydrologic Rules):**
  - **Machine Learning Model:** ใช้ 16 ฟีเจอร์ รวมทั้ง **Extended Upstream Lags (6, 12, 24, 48 ชม.)** สะท้อนเวลาเดินทางจริงของมวลน้ำ 120–150 กม. จากศรีสะเกษถึงอุบลฯ ทำนายระดับน้ำล่วงหน้า 6 ชั่วโมง ($R^2 = 0.9996$, $\text{MAE} = 0.0132\text{ ม.}$)
  - **Anomaly Safety Net:** ดักจับน้ำหลากเฉียบพลัน (Flash Flood: น้ำขึ้นเร็ว $>0.5\text{ ม./ชม.}$) และน้ำหนุนท้ายน้ำระบายช้า (Backwater Effect)
  - **Early Warning Hit Rate:** พิสูจน์ด้วยข้อมูลย้อนหลังจริงว่าสามารถส่งสัญญาณเตือนภัยล่วงหน้า 6 ชม. สำเร็จถึง **98.8% – 99.4%** โดยมีอัตราเตือนหลอกเป็น 0
- **📊 Triple-Tier Visualization & Simulation:**
  - **Plotly.js Interactive Chart:** ซูมดูรายชั่วโมง (Box Zoom), แถบเลื่อนเวลา (Range Slider), ชี้เมาส์ดูระดับจริง vs AI vs ผลต่าง
  - **Dual-Panel Static Image:** ภาพนิ่ง 2 ชั้น (ชั้นบนภาพรวม / ชั้นล่างเจาะซูม 72 ชม. ช่วงพีคน้ำสูงสุด)
  - **4 Simulation Modes:** Benchmark ข้อมูลจริง, จำลอง Flash Flood, จำลอง Backwater, และจำลองมหาอุทกภัย
- **💬 LINE Bot Integration:** แจ้งเตือนอัตโนมัติ (LINE Multicast พร้อมระบบ Anti-Spam), เมนูเช็คสถานะน้ำแบบ Quick Reply, คาดการณ์ระดับน้ำล่วงหน้า, และ Flex Message ข้อมูลติดต่อฉุกเฉิน
- **⚙️ Modern Admin Panel:** ควบคุมคำสั่งระบบผ่าน UI พร้อม **ปุ่มยกเลิกคำสั่ง (Cancel Subprocess)**, ตัวกรองช่วงเวลา (All Time, รายปี, รายเดือน, กำหนดวันเอง), และแก้ไขเกณฑ์เตือนภัยสถานี
- **🔄 Automated Scraper:** มี **GitHub Actions Workflow** ดึงข้อมูลอัตโนมัติทุก 15 นาที พร้อม Background Fallback บนเซิร์ฟเวอร์

---

## 🛠️ เทคโนโลยีและเครื่องมือ (Tech Stack)

| ส่วนประกอบ | เทคโนโลยีที่เลือกใช้ | รายละเอียด |
| :--- | :--- | :--- |
| **Backend Framework** | Python 3.13 / Django 5.2.6 | สถาปัตยกรรม MVT พร้อมระบบ Management Commands |
| **Database** | TiDB Serverless (Cloud) / MySQL (Dev) | รองรับ MySQL Protocol เชื่อมต่อผ่าน Pure-Python `PyMySQL` พร้อม SSL |
| **Machine Learning** | `scikit-learn`, `pandas`, `numpy`, `joblib` | การเตรียมข้อมูล Time-Series, Feature Lags, K-Fold CV, Linear Model |
| **Visualization** | `Plotly.js` (Web UI), `matplotlib` (Headless Agg) | กราฟ Interactive โต้ตอบได้ และภาพนิ่งสรุปผลความละเอียดสูง |
| **Web Server (Prod)** | `gunicorn==26.0.0`, `whitenoise==6.11.0` | WSGI Server ระดับ Production และ Static Files Caching |
| **Messaging & Bot** | LINE Messaging API (`line-bot-sdk==3.19.0`) | Webhook Callback, Multicast Alert, Quick Reply, Flex Messages |
| **Task Automation** | GitHub Actions (`.github/workflows/scraper.yml`) | รัน Cron Job ดึงข้อมูลทุก 15 นาทีแบบไร้ค่าใช้จ่าย |
| **Hosting Platform** | Render (Web Service Free Tier) | Host แอปพลิเคชันและ Admin Panel |

---

## 📂 โครงสร้างโปรเจกต์ (Project Structure)

```text
UFAsite/
├── .github/
│   └── workflows/
│       └── scraper.yml             # GitHub Actions ดึงข้อมูลอัตโนมัติทุก 15 นาที
├── UFAsite/                        # Django Project Root
│   ├── build.sh                    # สคริปต์ Build สำหรับ Render (Collectstatic + Migrate)
│   ├── manage.py                   # สคริปต์หลักจัดการ Django
│   ├── requirements.txt            # สำเนา Dependencies สำหรับ Render Root Directory
│   ├── trained_model.joblib        # ไฟล์โมเดล Machine Learning ที่เทรนแล้ว
│   ├── UFAsite/
│   │   ├── settings.py             # การตั้งค่าระบบ (Database, Auto .env Loader, Static, Security)
│   │   ├── urls.py                 # URL Routing ระดับระบบ
│   │   └── wsgi.py                 # WSGI Application Entry Point
│   ├── pages/                      # แอปพลิเคชันหลัก (Core App)
│   │   ├── models.py               # Models: WaterStations, WaterLevels, LineUsers, LineMessages
│   │   ├── predictor.py            # โมดูลพยากรณ์ AI 16 Features + กฎ Anomaly Detection
│   │   ├── risk_calculator.py      # คำนวณระดับความเสี่ยง (ปกติ, เฝ้าระวัง, วิกฤต) ตามเกณฑ์สถานี
│   │   ├── updater.py              # APScheduler Background Service
│   │   ├── line_handlers/          # โมดูลย่อยจัดการคำสั่ง LINE Bot
│   │   │   ├── emergency.py        # ข้อมูลติดต่อฉุกเฉิน (Flex Message)
│   │   │   ├── prediction.py       # ตอบกลับผลพยากรณ์ล่วงหน้า
│   │   │   ├── subscription.py     # ลงทะเบียนรับ/ยกเลิกการแจ้งเตือน
│   │   │   └── water_status.py     # ตรวจสอบระดับน้ำสดรายสถานี
│   │   ├── management/commands/    # คำสั่ง Django Management Commands
│   │   │   ├── scrape_data.py      # ดึงข้อมูลสดจาก ThaiWater API + ส่งแจ้งเตือน LINE
│   │   │   ├── import_historical_data.py # นำเข้าข้อมูลย้อนหลังจาก ThaiWater API
│   │   │   ├── simulation.py       # ทดสอบโมเดล, K-Fold, Lead Time Audit, สร้างกราฟ
│   │   │   └── train_model.py      # เทรนโมเดลใหม่จากข้อมูลประวัติศาสตร์ทั้งหมด
│   │   └── views/                  # View Controllers
│   │       ├── admin_views.py      # จัดการ Admin Panel, รันคำสั่ง, ยกเลิกคำสั่ง, API Data
│   │       ├── line_views.py       # LINE Webhook Signature Verification & Router
│   │       └── web_views.py        # หน้าแรกแสดงระดับน้ำสาธารณะ
│   ├── static/                     # ไฟล์ Static (CSS, Images, JSON Data)
│   │   └── images/
│   │       ├── evaluation_data.json # ชุดข้อมูลผลการประเมินสำหรับ Plotly.js
│   │       └── evaluation_plot.png  # ภาพกราฟ Matplotlib 2 ชั้น
│   └── templates/                  # Django HTML Templates
│       ├── home.html               # หน้าแรกสาธารณะ
│       └── admin_panel/            # หน้าจอควบคุมสำหรับผู้ดูแลระบบ
│           ├── base_admin.html     # โครงร่าง Admin Base Template
│           ├── commands.html       # แดชบอร์ดคำสั่งระบบ + กราฟ Interactive + ปุ่มยกเลิก
│           ├── dashboard.html      # ภาพรวม KPI และสถิติระดับน้ำ
│           └── stations.html       # ตารางรายการสถานีและปรับเกณฑ์เตือนภัย
├── .env.example                    # ตัวอย่างการตั้งค่าตัวแปรสภาพแวดล้อม
├── .gitignore                      # ป้องกันไฟล์ Secret / Database หลุดขึ้น Git
├── get_api_ids.py                  # สคริปต์ Utility ตรวจสอบ API ID ของ ThaiWater
├── README.md                       # เอกสารคู่มือระบบ
└── requirements.txt                # รายการ Dependencies หลักของโปรเจกต์
```

---

## 🌐 เส้นทางและจุดเชื่อมต่อ (Endpoints)

| Method | Endpoint | สิทธิ์เข้าถึง | หน้าที่การทำงาน |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | ทุกคน | หน้าแรกแสดงระดับน้ำล่าสุดทั้ง 3 สถานี พร้อมสถานะความเสี่ยง |
| `POST` | `/webhook/` | LINE Platform | รับ Webhook Event จาก LINE Messaging API และประมวลผลคำสั่ง |
| `GET` | `/admin-panel/` | Admin | หน้าแดชบอร์ดภาพรวม สถิติสถานี และระดับน้ำล่าสุด |
| `GET` | `/admin-panel/stations/` | Admin | ตารางรายการสถานีวัดน้ำ |
| `GET/POST`| `/admin-panel/stations/<id>/edit/` | Admin | แก้ไขระดับเตือนภัย (Warning), วิกฤต (Critical), และสถานะเปิด/ปิด |
| `GET` | `/admin-panel/commands/` | Admin | หน้าแดชบอร์ดรันคำสั่งระบบ ดูผลลัพธ์ และแสดงกราฟ Interactive |
| `POST` | `/admin-panel/run-command/` | Admin | สั่งรัน Django Management Command แบบอะซิงโครนัส |
| `POST` | `/admin-panel/cancel-command/` | Admin | ส่งสัญญาณยุติการทำงาน (Kill Process Tree) ทันที |

---

## 💻 การติดตั้งและเริ่มต้นใช้งาน (Quick Start)

### 1. โคลนคลังข้อมูล (Clone Repository)
```bash
git clone https://github.com/AphiratNiyom/UFA_Deploy.git
cd "Final Project"
```

### 2. สร้าง Virtual Environment และติดตั้ง Dependencies
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# ติดตั้ง Dependencies
pip install -r requirements.txt
```

### 3. ตั้งค่าตัวแปรสภาพแวดล้อม (Environment Setup)
คัดลอกไฟล์ `.env.example` เป็น `.env` และกรอกข้อมูลของคุณ:
```bash
cp .env.example .env
```
*(ดูรายละเอียดค่าตัวแปรได้ในส่วน [ความปลอดภัยและการจัดการตัวแปรสภาพแวดล้อม](#-ความปลอดภัยและการจัดการตัวแปรสภาพแวดล้อม))*

### 4. ดำเนินการ Database Migration
```bash
python UFAsite/manage.py migrate
```

### 5. รันเซิร์ฟเวอร์สำหรับพัฒนา (Development Server)
```bash
python UFAsite/manage.py runserver
```
เปิดเบราว์เซอร์ไปที่: `http://127.0.0.1:8000/` หรือ `http://127.0.0.1:8000/admin-panel/`

---

## ⌨️ คำสั่งระบบ (Management Commands)

### 1. ดึงข้อมูลสดจาก API (`scrape_data`)
ดึงระดับน้ำล่าสุดของสถานี M.7, M.5, และ M.11B บันทึกลงฐานข้อมูล และส่งการแจ้งเตือน LINE หากแตะระดับวิกฤต:
```bash
python UFAsite/manage.py scrape_data
```

### 2. นำเข้าข้อมูลประวัติศาสตร์ย้อนหลัง (`import_historical_data`)
ดึงข้อมูลย้อนหลังจาก ThaiWater API ตามช่วงวันที่กำหนด พร้อมระบบตรวจจับข้อมูลซ้ำซ้อนอัตโนมัติ:
```bash
# ตัวอย่าง: ดึงข้อมูลสถานี M.7 (TS16, API ID: 1400) เดือนกันยายน 2024
python UFAsite/manage.py import_historical_data --station_id TS16 --station_code 1400 --start 2024-09-01 --end 2024-09-30

# สถานี M.5 (TS2, API ID: 1398)
python UFAsite/manage.py import_historical_data --station_id TS2 --station_code 1398 --start 2024-08-01 --end 2024-10-31

# สถานี M.11B (TS5, API ID: 1402)
python UFAsite/manage.py import_historical_data --station_id TS5 --station_code 1402 --start 2024-08-01 --end 2024-10-31
```

### 3. เทรนโมเดล AI ใหม่ (`train_model`)
นำข้อมูลประวัติศาสตร์ทั้งหมดในฐานข้อมูลมาประมวลผล Feature Engineering และบันทึกลง `trained_model.joblib`:
```bash
python UFAsite/manage.py train_model
```

### 4. ทดสอบและประเมินโมเดล (`simulation`)
ประเมินความแม่นยำทางสถิติ ($R^2$, $\text{MAE}$, K-Fold), ตรวจสอบอัตราการเตือนภัยล่วงหน้า (Early Warning Hit Rate), และส่งออกกราฟผลลัพธ์:
```bash
# ทดสอบกับข้อมูลทั้งหมด (All Time)
python UFAsite/manage.py simulation

# เลือกเฉพาะปี
python UFAsite/manage.py simulation --year 2024

# เลือกเฉพาะเดือนและปี (เช่น กันยายน 2024)
python UFAsite/manage.py simulation --year 2024 --month 9

# กำหนดช่วงวันที่เอง
python UFAsite/manage.py simulation --start 2024-08-15 --end 2024-10-15

# ทดสอบสถานการณ์จำลอง (Scenarios)
python UFAsite/manage.py simulation --mode flash_flood  # น้ำเหนือหลากฉับพลัน
python UFAsite/manage.py simulation --mode backwater    # น้ำหนุนระบายช้า
python UFAsite/manage.py simulation --mode simulate     # มหาอุทกภัย
```

### 5. รันแบบทดสอบระบบ (Automated Tests)
```bash
python UFAsite/manage.py test pages
```

---

## 🧠 สถาปัตยกรรมโมเดล AI และอุทกวิทยา

### 1. ฟีเจอร์ที่ใช้ในการทำนาย (16 Features)
เพื่อสะท้อนพฤติกรรมจริงของแม่น้ำมูล โมเดลได้รับการออกแบบให้รับข้อมูลครอบคลุมทั้งระยะสั้นและระยะไกล:
1. **ระดับน้ำปัจจุบัน:** `TS2`, `TS16`, `TS5`
2. **โมเมนตัมระยะสั้น 1–3 ชม. (Short-term Trend):**
   - `TS2_lag1h`, `TS2_lag2h`, `TS2_lag3h`
   - `TS16_lag1h`, `TS16_lag2h`, `TS16_lag3h`
   - `TS5_lag1h`, `TS5_lag2h`, `TS5_lag3h`
3. **ระยะเวลาเดินทางของมวลน้ำ 6–48 ชม. (Extended Upstream Lags):**
   - `TS2_lag6h`, `TS2_lag12h`, `TS2_lag24h`, `TS2_lag48h`  
   *(ระยะทางจากสถานี M.5 ราษีไศล ถึง M.7 เมืองอุบลฯ อยู่ที่ 120–150 กม. คลื่นน้ำหลากเดินทางด้วยความเร็ว ~2–3 กม./ชม. ใช้เวลา 1–2 วัน ข้อมูลชุดนี้จึงเป็นตัวบอกสัญญาณน้ำล่วงหน้าตามธรรมชาติ)*

### 2. ผลการประเมินความแม่นยำ (Model Benchmark)
จากการทดสอบกับข้อมูลจริงกว่า 24,000 ชั่วโมง:
- **ค่าเฉลี่ย K-Fold $R^2$ Score:** `0.9996` (ความสอดคล้องของแนวโน้มระดับน้ำ)
- **ค่าความคลาดเคลื่อนเฉลี่ย (MAE):** `0.0132 เมตร` (คลาดเคลื่อนเพียง ~1.3 เซนติเมตร)
- **Early Warning Hit Rate:** `98.8% – 99.4%` (ทำนายและแจ้งเตือนนำหน้าน้ำจริง 6 ชม. ล่วงหน้าสำเร็จ)
- **False Alarm (เตือนหลอก):** `0 ครั้ง` ในช่วงฤดูน้ำหลาก

---

## 🖥️ ระบบบริหารจัดการ Admin Panel

เข้าใช้งานผ่านเส้นทาง: `/admin-panel/commands/`

```text
┌────────────────────────────────────────────────────────────────────────┐
│  🖥️ Django Management Commands Dashboard                                │
│  [▶ รันคำสั่ง]  [⏹ ยกเลิกคำสั่ง]  [● สถานะการทำงาน]                      │
├────────────────────────────────────────────────────────────────────────┤
│  Output Log: Terminal Display (แสดงผลเรียลไทม์)                         │
├────────────────────────────────────────────────────────────────────────┤
│  📊 Model Evaluation Visualization                                      │
│  [📊 กราฟ Interactive (ซูม/ลาก)]  [🖼️ ภาพนิ่ง (Overview+72h)]  [🔍 เต็มจอ]│
│                                                                        │
│  - R² Score: 0.9996  |  MAE: 0.0132 m  |  เตือนล่วงหน้า: 6 ชม. (Hit: 99.4%)│
│  - Plotly Interactive Chart: คลิกลากซูมอิสระ + Mini Timeline Slider    │
└────────────────────────────────────────────────────────────────────────┘
```

- **⏹ ปุ่มยกเลิกคำสั่ง (Process Killer):** สามารถกดยกเลิกคำสั่งที่กำลังรันอยู่ได้ตลอดเวลา ระบบจะส่งสัญญาณ `taskkill /F /T` (Windows) หรือ `SIGTERM/SIGKILL` (Linux) เพื่อปิด Process Tree ทันที ไม่ค้างหน่วยความจำ
- **🗓️ Simulation Period Modal:** หน้าต่าง Pop-up ให้เลือกช่วงเวลาทดสอบได้อย่างอิสระ (All Time / เลือกปี 2024–2026 / เลือกเดือน / กำหนดวันที่เริ่มต้น-สิ้นสุด)
- **🔍 Fullscreen Lightbox Modal:** คลิกที่ภาพนิ่งเพื่อเปิดดูแผนภูมิความละเอียดสูงขนาดเต็มหน้าจอ

---

## ☁️ การติดตั้งบนระบบ Production (Render Deployment)

โปรเจกต์รองรับการ Deploy บน **Render (Free Tier)** ได้อย่างสมบูรณ์แบบ:

1. **สร้าง Web Service บน Render:**
   - **Repository:** เชื่อมต่อกับ GitHub Repository ของโปรเจกต์
   - **Root Directory:** ให้เว้นว่างไว้ (หรือใส่ `.` เพื่อใช้ Root)
   - **Environment:** `Python 3`
   - **Build Command:**
     ```bash
     chmod +x ./UFAsite/build.sh && ./UFAsite/build.sh
     ```
   - **Start Command:**
     ```bash
     cd UFAsite && gunicorn UFAsite.wsgi:application
     ```

2. **การทำงานอัตโนมัติของ Scraper บน Render Free Tier:**
   - เนื่องจาก Render Free Tier จะเข้าสู่โหมดหลับ (Spin down) เมื่อไม่มี HTTP Request นานเกิน 15 นาที ทำให้ Background Scheduler ภายในแอปอาจหยุดชั่วคราว
   - ระบบจึงใช้ **GitHub Actions (`.github/workflows/scraper.yml`)** ทำหน้าที่เป็นตัวกระตุ้นหลัก โดยจะรันคำสั่ง `scrape_data` ทุก 15 นาทีจากภายนอกอย่างแม่นยำและเสถียร 100%

---

## 🔐 ความปลอดภัยและการจัดการตัวแปรสภาพแวดล้อม

โปรเจกต์ใช้ระบบ **Pure-Python `.env` Loader** ที่ติดตั้งมาในตัว โดยจะโหลดตัวแปรจากไฟล์ `.env` อัตโนมัติเมื่ออยู่ในเครื่อง Development และอ่านค่าจาก System Environment Variables เมื่ออยู่บน Render

### รายการตัวแปรสภาพแวดล้อมที่รองรับ:

```ini
# Django Security
SECRET_KEY=your-django-secret-key-here
DEBUG=True                       # บน Render ให้ตั้งเป็น False อัตโนมัติ
ALLOWED_HOSTS=localhost,127.0.0.1,your-app.onrender.com

# TiDB Serverless (MySQL-Compatible Production Database)
TIDB_HOST=gateway01.ap-southeast-1.prod.aws.tidbcloud.com
TIDB_PORT=4000
TIDB_USER=your_tidb_user.root
TIDB_PASSWORD=your_tidb_password
TIDB_DATABASE=ufa_flood_db

# LINE Messaging API Credentials
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token_here
LINE_CHANNEL_SECRET=your_line_channel_secret_here

# Local Development Fallback Database (Optional)
DB_NAME=ufa_db
DB_USER=root
DB_PASSWORD=your_local_password
DB_HOST=127.0.0.1
DB_PORT=3306

# System Configurations
ENABLE_SCHEDULER=True            # เปิด/ปิด Background Scheduler ตอนรัน Unit Tests
```

> [!CAUTION]
> **ข้อควรระวังด้านความปลอดภัย**: ห้าม Commit ไฟล์ `.env` ขึ้น Git เป็นอันขาด ให้ใช้ไฟล์ `.env.example` เป็นแม่แบบเท่านั้น โดยไฟล์ `.gitignore` ได้รับการกำหนดค่าให้เพิกเฉยต่อ `.env` เรียบร้อยแล้ว

---

## 👥 ผู้พัฒนาและลิขสิทธิ์ (Authors & License)
- **ผู้พัฒนา:** Aphirat Niyom & Google DeepMind Antigravity Pair Programmer
- **ลิขสิทธิ์:** สำหรับการศึกษา วิจัย และพัฒนาระบบเฝ้าระวังภัยพิบัติชุมชน
