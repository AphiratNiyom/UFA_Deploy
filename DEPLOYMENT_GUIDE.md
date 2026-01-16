# คู่มือการ Deploy โปรเจค UFASite (Django)

เอกสารนี้จะอธิบายแนวทางการ Deploy โปรเจค Django ของคุณ โดยเน้นไปที่การนำไปลง Server ของตัวเอง (Ubuntu VPS หรือ On-premise Server) ตามที่สอบถามมา

## 1. ทางเลือกในการ Deploy (Deployment Options)

โปรเจคของคุณมีการเตรียมไฟล์สำหรับ **Render** ไว้แล้ว (`build.sh`, `gunicorn_config.py`) ซึ่งสะดวกมาก แต่ถ้าต้องการลง Server ของตัวเอง จะมีข้อดีเรื่องการควบคุมทรัพยากรและราคาในระยะยาว

| วิธีการ | เหมาะสำหรับ | ความยาก |
| :--- | :--- | :--- |
| **Cloud PaaS (Render/Railway)** | ผู้เริ่มต้น, โปรเจคทดสอบ, ไม่อยากดูแล Server | ง่าย (มี config ไว้แล้ว) |
| **Self-Hosted / VPS (Own Server)** | Production จริงจัง, ต้องการ Performance สูง, คุม Cost เอง | ปานกลาง-ยาก (ต้องดูแล OS เอง) |
| **Docker / Docker Compose** | ทีมพัฒนาหลายคน, ต้องการ Environment ที่เหมือนกันเป๊ะๆ | ปานกลาง (ต้องเขียน Dockerfile เพิ่ม) |

---

## 2. การ Deploy บนเครื่อง Server ของตัวเอง (Own Server)

หากคุณเลือกที่จะ Deploy ลง Server ของตัวเอง (เช่น DigitalOcean, cloud provider ในไทย, หรือเครื่อง PC ที่บ้านที่ทำ Fixed IP) นี่คือสิ่งที่คุณต้องเตรียมและทำความเข้าใจ

### 2.1 สเปค Server ที่แนะนำ (Server Requirements)
เนื่องจากโปรเจคมีการใช้ Library ด้าน Data Science (`pandas`, `numpy`, `scikit-learn`) ซึ่งบริโภค RAM ค่อนข้างมากในขณะทำงาน (Load Model / Predict)

*   **OS:** Ubuntu 22.04 LTS หรือ 24.04 LTS (แนะนำ Ubuntu เพราะหาคู่มือง่ายที่สุดสำหรับ Django)
*   **CPU:** 2 vCPU ขึ้นไป (1 Core อาจจะช้าตอนรัน Model)
*   **RAM:** **ขั้นต่ำ 2GB** (แนะนำ 4GB จะลื่นไหลกว่ามาก ถ้ามี Database อยู่ในเครื่องเดียวกัน)
*   **Storage:** 20GB SSD ขึ้นไป
*   **Network:** ต้องมี Public IP และเปิด Port 80, 443 ได้

### 2.2 โครงสร้างระบบ (Architecture)
เราจะใช้ท่ามาตรฐานที่เป็น Best Practice สำหรับ Python Production:
1.  **Nginx**: อยู่หน้าด่าน คอยรับ Request จากผู้ใช้ (Port 80/443) แล้วส่งต่อให้ Gunicorn
2.  **Gunicorn**: เป็น App Server ที่รัน Django Code (คุณมี `gunicorn_config.py` อยู่แล้ว เยี่ยมมาก แต่ต้องแก้ `workers` ถ้า Server แรงขึ้น)
3.  **MySQL / MariaDB**: ฐานข้อมูล (ติดตั้งในเครื่องเดียวกันหรือแยกก็ได้)
4.  **Supervisor / Systemd**: ตัวคุม Process ให้ Gunicorn รันอยู่ตลอดเวลา ถ้าดับให้เปิดใหม่เอง

---

## 3. ขั้นตอนการติดตั้ง (Step-by-Step Guide)

สมมติว่าคุณได้เครื่อง Server ที่เป็น **Ubuntu 22.04** มาแล้ว ให้ทำตามขั้นตอนคร่าวๆ ดังนี้:

### Step 1: เตรียมเครื่องและติดตั้ง Package พื้นฐาน
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv python3-dev libmysqlclient-dev nginx git -y
```

### Step 2: ติดตั้ง Database (ถ้าใช้ MySQL ในเครื่อง)
```bash
sudo apt install mysql-server
sudo mysql_secure_installation
# จากนั้นสร้าง Database และ User ให้ตรงกับ settings.py ของคุณ
# (แนะนำให้เปลี่ยนรหัสผ่านและสร้าง User ใหม่ที่ไม่ใช่ root เพื่อความปลอดภัย)
```

### Step 3: ดึง Code และสร้าง Environment
```bash
cd /var/www
sudo git clone <YOUR_REPO_URL> ufasite
cd ufasite
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 4: ตั้งค่า Environment Variables
ใน `settings.py` ของคุณมีการอ่านค่าจาก `os.environ` ดังนั้นบน Server คุณควรสร้างไฟล์ `.env` หรือตั้งค่าใน Systemd service
*   `SECRET_KEY`
*   `DEBUG=False` (สำคัญมาก! ห้ามเปิด True บน Production)
*   `TIDB_...` หรือค่า Database Connection ต่างๆ

### Step 5: จัดการ Static Files และ Database
```bash
python manage.py collectstatic
python manage.py migrate
```

### Step 6: ทดลองรัน Gunicorn
```bash
gunicorn --config UFAsite/gunicorn_config.py UFAsite.wsgi
# ถ้าไม่มี Error แสดงว่า Code พร้อมรัน
```

### Step 7: สร้าง Systemd Service (เพื่อให้รันอัตโนมัติเมื่อเปิดเครื่อง)
สร้างไฟล์ `/etc/systemd/system/ufasite.service`:
```ini
[Unit]
Description=Gunicorn daemon for UFASite
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/var/www/ufasite/UFAsite
ExecStart=/var/www/ufasite/venv/bin/gunicorn --config gunicorn_config.py UFAsite.wsgi

[Install]
WantedBy=multi-user.target
```
สั่งรัน: `sudo systemctl start ufasite` และ `sudo systemctl enable ufasite`

### Step 8: ตั้งค่า Nginx
สร้างไฟล์ `/etc/nginx/sites-available/ufasite`:
```nginx
server {
    listen 80;
    server_name your_domain_or_ip.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    # เสิร์ฟ Static File (สำคัญมาก เพราะปิด Debug=True แล้ว Django จะไม่เสิร์ฟเอง)
    location /static/ {
        root /var/www/ufasite/UFAsite/staticfiles;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock; # หรือ http://127.0.0.1:8000
    }
}
```
อย่าลืม Link และ Restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/ufasite /etc/nginx/sites-enabled
sudo systemctl restart nginx
```

---

## 4. ข้อควรระวัง (Checklist)
1.  **Debug Mode**: ต้องตั้ง `DEBUG = False` ใน `settings.py` เสมอเมื่ออยู่บน Production
2.  **Secret Key**: อย่าใช้ Key เดียวกับที่หลุดใน git, ให้ Gen ใหม่และเก็บเป็นความลับ
3.  **Allowed Hosts**: ใน `settings.py` ต้องเพิ่ม IP ของ Server หรือ Domain Name ลงไปใน `ALLOWED_HOSTS`
    ```python
    ALLOWED_HOSTS = ['your-domain.com', 'your.server.ip.address']
    ```
4.  **Database**: ข้อมูลใน `runserver` (Local) จะไม่ตามไปที่ Server ใหม่ คุณต้อง Backup & Restore ข้อมูลไปเองถ้าต้องการข้อมูลเก่า
