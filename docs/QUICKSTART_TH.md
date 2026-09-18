# Quick Start — คู่มือผู้ใช้ Team Engineering Skills

สำหรับสมาชิกทีม • ชุดปลั๊กอิน 2.1.0 • ตรวจเอกสารทางการ 17 กันยายน 2026
อ่านหน้านี้และเฉพาะ Tool ที่คุณใช้ ใช้เวลาประมาณ 5 นาทีเมื่อบัญชีและโปรเจกต์พร้อม

**ได้ประโยชน์อะไร?** เป็นชุดแนวทาง 15 Skills ให้ AI ช่วยวิเคราะห์ Requirement ออกแบบ UI และสร้าง Test Case ตามมาตรฐานทีม ลดการพิมพ์คำสั่งซ้ำและช่วยตรวจย้อนกลับถึงความต้องการ ไม่ใช่การฝึกโมเดลใหม่ และยังต้องตรวจคำตอบก่อนใช้งานจริง

**ก่อนเริ่ม:** ขอชุดติดตั้ง/ลิงก์และเลขรุ่นที่ทีมอนุมัติจากผู้ดูแล ชุดที่ตรวจในงานนี้คือ **2.1.0 / commit `5fe5e20` สำหรับ pilot** ไม่ใช่คำยืนยันว่าเป็นรุ่นล่าสุดตลอดไป ยังไม่ได้ยืนยันการเผยแพร่ชุดทีมใน ChatGPT Workspace หรือ Claude Skills

| Tool | ติดตั้งครั้งแรก | เปลี่ยนเครื่อง | Skill Update | วิธีเช็ค Version |
| --- | --- | --- | --- | --- |
| [ChatGPT](#chatgpt) | ต่อบัญชี/Workspace เมื่อทีมแชร์ให้ | บัญชี/Workspace เดิม แล้วเช็ค Installed | แบบ Workspace Git sync: ผู้ดูแล sync; คุณเปิดแชตใหม่ | คำถามตรวจหลักฐานด้านล่าง; อ่านรุ่นไม่ได้ให้ผู้ดูแลยืนยัน |
| [Codex](#codex) | แบบ local: ต่อเครื่อง/ผู้ใช้; ทีมเตรียมโปรเจกต์ครั้งเดียว | ติดตั้ง local ใหม่ ไม่ถือว่า login แล้ว sync | รับชุดใหม่; local ไม่ดึง ZIP ใหม่เอง; เปิดแอป/session ใหม่ | คำถามตรวจหลักฐานจากแพ็กเกจที่โหลด |
| [Claude](#claude) | ต่อบัญชี/องค์กร: เปิด shared skill หรืออัปโหลด ZIP ราย Skill | บัญชี/องค์กรเดิม แล้วเช็คว่าเปิดอยู่ | Shared: รุ่นใหม่เมื่อใช้ครั้งถัดไป; อัปโหลดเอง: รับไฟล์ใหม่ | ดูรายละเอียด Skill เทียบประกาศทีม; ไม่มีเลขให้ถามผู้ดูแล |
| [Claude Code](#claude-code) | marketplace local: ต่อเครื่อง/ผู้ใช้ | ติดตั้งใหม่; ไม่พึ่ง account sync | รับชุดใหม่ → update → `/reload-plugins` | `claude plugin list` เทียบประกาศทีม |

**ลองสั่ง:** “ช่วยวิเคราะห์ requirement นี้และสร้าง test case แยกคำถามที่ยังไม่ชัด และอย่าใส่ผล PASS ก่อนรันทดสอบจริง” ไม่ต้องเลือก Skill เองเมื่อ Tool โหลด Skills ได้; ถ้าไม่พบให้ AI แจ้ง ไม่ใช่อ้างว่าใช้งานแล้ว

**คำถามตรวจหลักฐาน** (คัดลอกใช้ในแชตใหม่):
> แสดงเวอร์ชัน Team Engineering Skills ที่ session นี้โหลดจริง พร้อมชื่อไฟล์หรือรายละเอียดการติดตั้งที่ยืนยันได้ แยกเวอร์ชันปลั๊กอินกับ Skill ที่ใช้ ถ้าเข้าถึงหลักฐานไม่ได้ให้ตอบว่า “ตรวจสอบไม่ได้” ห้ามใช้เลขจากคู่มือหรือความจำ

เทียบกับ **ประกาศรุ่นที่ทีมอนุมัติ** เสมอ; `codex --version` / `claude --version` คือรุ่นแอป ไม่ใช่รุ่น Skills ใช้เฉพาะข้อมูลที่องค์กรอนุญาต ห้ามแนบรหัสผ่านหรือข้อมูลลูกค้าโดยไม่ได้รับอนุญาต

---

## ChatGPT

### 1. Install

**ทำต่อบัญชี/Workspace ไม่ใช่ต่อ Project หรือเครื่อง** สำหรับช่องทาง Workspace ที่ทีมแชร์ให้:
Step 1 → เข้าบัญชีและ Workspace ของทีม
Step 2 → เปิด **Plugins** เลือกรายการของ Workspace ค้นหา `team-engineering-skills` แล้วกดติดตั้ง
Step 3 → เปิดแชตใหม่ ถ้าทีมแจกเป็น Skill แยก ให้ใช้ **Plugins → Skills → Shared with me / Shared by workspace → Install** แทน

ถ้าไม่พบรายการ ให้ขอลิงก์จากผู้ดูแล: GitHub public ไม่ได้แปลว่ามีใน Directory แล้ว **อย่าอัปโหลด ZIP marketplace ทั้งชุดแทน Skill** ยังไม่ยืนยันช่องทางทีมนี้ในบัญชีจริง

Skills ใน ChatGPT ขึ้นกับสิทธิ์ Workspace และบัญชี Business, Enterprise, Healthcare หรือ Edu ที่เข้าเกณฑ์; อย่าเหมารวมว่า Free/Plus/Pro มีเมนูเดียวกัน เปลี่ยนเครื่องให้ใช้บัญชี/Workspace เดิมและตรวจ Installed ก่อน ไม่ต้องลง ZIP local ตามวิธี Codex [เอกสาร Skills](https://help.openai.com/en/articles/20001066)

### 2. Use

> ช่วยวิเคราะห์ requirement นี้ แล้วสร้าง test case ตามมาตรฐานทีม หากยังไม่ได้โหลด Skills ของทีมให้แจ้งก่อน

ระบบเลือก Skills ที่เกี่ยวข้องได้เมื่อมีให้ใช้ ไม่ต้องจิ้มเลือกทีละงาน [วิธีใช้ Plugins](https://learn.chatgpt.com/docs/plugins)

### 3. Update Skill

ถ้าทีมเผยแพร่ผ่าน Workspace Git sync: ผู้ดูแลจัดการ sync คุณไม่ต้อง Git Pull; หลังทีมยืนยัน sync แล้วให้เปิดแชตใหม่ ไม่ต้อง restart เครื่อง การปัก commit จะไม่ตาม commit ใหม่เอง สำหรับ Skill ที่อัปโหลด/คัดลอกเอง **อย่าถือว่า sync กับ GitHub** ให้รับรุ่นใหม่ตามประกาศทีม [การ sync](https://learn.chatgpt.com/docs/enterprise/plugin-management)

### 4. Verify

ใช้ **คำถามตรวจหลักฐานใน Quick Start** แล้วเทียบประกาศทีม ถ้า Tool อ่าน manifest/รายละเอียดรุ่นไม่ได้ ถือว่า **ยังยืนยันรุ่นไม่ได้** ส่งชื่อรายการและ Workspace ให้ผู้ดูแลตรวจ ไม่ใช้คำตอบ AI ที่ไม่มีหลักฐานเป็นคำยืนยัน

---

## Codex

### 1. Install

**วิธีนี้เป็น local marketplace: ทำครั้งเดียวต่อเครื่องและผู้ใช้ OS** ไม่ใช่ครั้งเดียวต่อบัญชี; ใช้ macOS หรือ Windows ที่มี client รองรับ Plugins

Step 1 → รับ ZIP ที่ทีมอนุมัติ แตกลงโฟลเดอร์ถาวร แล้วคัดลอก path โฟลเดอร์ที่มี `.agents` และ `plugins`
Step 2 → เปิด Terminal (macOS) หรือ PowerShell (Windows) พิมพ์คำสั่งนี้ โดยแทนข้อความในเครื่องหมายคำพูดด้วย path จริง:

```sh
codex plugin marketplace add "ABSOLUTE_PATH_TO_EXTRACTED_MARKETPLACE"
```

Step 3 → เปิดแอปใหม่ ไป **Plugins** เลือก marketplace ของทีม ติดตั้ง `team-engineering-skills` แล้วเริ่ม session ใหม่; CLI ที่รองรับใช้ `/plugins` ได้ ถ้าไม่มีคำสั่งหรือเมนูให้ผู้ดูแลช่วยตั้งค่ารุ่นที่รองรับ ไม่ใช่ติดตั้งจาก IDE extension ซึ่งยังไม่รองรับ Plugins [คู่มือ Plugins](https://learn.chatgpt.com/docs/plugins) · [Local marketplace](https://developers.openai.com/plugins/build/plugins)

**ต่อ Project:** เปิดโฟลเดอร์ที่ทีมเตรียม `AGENTS.md`, `CLAUDE.md`, `.team-ai` ไว้แล้ว ถ้ายังไม่มีให้ขอผู้ดูแลเตรียมครั้งเดียว ไม่สร้างทับเอง ทุกเครื่องต้องมีปลั๊กอิน แม้ดึงไฟล์โปรเจกต์มาแล้ว

### 2. Use

> ช่วยวิเคราะห์ requirement นี้ ออกแบบหน้าจอ และสร้าง test case ที่อ้างอิงกัน ถ้าข้อมูลไม่พอให้ถาม

ไม่ต้องเลือก Skill เอง ตรวจว่า AI แจ้ง Skill ที่เกี่ยวข้องและอ่านคำสั่งโปรเจกต์ได้

### 3. Update Skill

Local ZIP **ไม่อัปเดตอัตโนมัติ**: รับ ZIP ใหม่ → ปิดแอป → เปลี่ยนชื่อโฟลเดอร์ชุดเดิมเติม `-backup` → สร้างโฟลเดอร์ใหม่ที่ **ชื่อและ path เดิม** แล้วแตกชุดใหม่ลงไป (ต้องเห็น `.agents` และ `plugins` ที่ระดับเดิม) → เปิดแอปและ session ใหม่ ไม่ต้องเพิ่ม marketplace ซ้ำหรือ Git Pull อย่าผสมไฟล์ใหม่ทับไฟล์เก่า ถ้าไม่ทราบ source path ให้ผู้ดูแลช่วยก่อน [วิธีอัปเดต local source](https://developers.openai.com/plugins/build/plugins)

### 4. Verify

ใช้ **คำถามตรวจหลักฐาน** ให้แสดง version จาก manifest/registry ของปลั๊กอินที่โหลดจริง ไม่ใช่จาก ZIP ใน Downloads หรือ `.team-ai` อย่างเดียว แล้วเทียบประกาศทีม ถ้ายังเห็นรุ่นเก่าให้ส่งผลนี้ให้ผู้ดูแล

---

## Claude

### 1. Install

**ทำต่อบัญชี/องค์กร ไม่ใช่ต่อเครื่องหรือ Project** ต้องเปิด Code execution and file creation; มี Skills ใน Free/Pro/Max/Team/Enterprise แต่สิทธิ์องค์กรอาจจำกัด

Step 1 → เข้า Claude บัญชี/องค์กรที่ถูกต้อง เปิด **Customize → Skills**
Step 2 → ถ้าทีมแชร์ให้ ให้เปิด Skill ใน **Shared with you**; ถ้าแจกไฟล์ ให้ **+ → Create skill → Upload a skill** เลือก ZIP ราย Skill ที่ผู้ดูแลเตรียม
Step 3 → ตรวจว่า Skill เปิดใช้งาน แล้วเริ่มแชตใหม่

**ยังไม่ได้แจก ZIP ราย Skill หรือ shared link สำหรับ Claude ในงานนี้** ต้องขอผู้ดูแลก่อน ห้ามใช้ ZIP marketplace ทั้งชุดแทนกัน เปลี่ยนเครื่องให้เข้าบัญชี/องค์กรเดิมและตรวจรายการที่เปิดอยู่ [เอกสาร Claude Skills](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

### 2. Use

> ช่วยวิเคราะห์ requirement นี้และสร้าง test case ตามมาตรฐานทีม แยกข้อเท็จจริงกับสมมติฐาน

เมื่อ Skill เปิดและตรงงาน Claude สามารถเลือกใช้เอง; ถ้าทำงานไม่ได้เพราะขาดไฟล์หรือเครื่องมือให้แจ้ง ไม่ถือว่าใช้แพ็กเกจ local ได้ครบทุกอย่าง

### 3. Update Skill

**Shared skill:** ผู้แชร์แก้แล้ว ผู้รับได้รุ่นใหม่เมื่อใช้ครั้งถัดไป ไม่ต้อง Pull/อัปโหลดซ้ำ
**อัปโหลดเอง:** รับ ZIP ราย Skill รุ่นใหม่จากทีมและอัปโหลดตาม Install ปิดตัวเก่าหากเกิดรายการซ้ำ แล้วเปิดแชตใหม่ ไม่ต้อง restart เครื่อง อย่าถือว่าไฟล์ส่วนตัวตามรุ่น shared ให้อัตโนมัติ [การสร้าง/ทดสอบ Skill](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)

### 4. Verify

เปิด **Customize → Skills → Skill ของทีม** ตรวจชื่อผู้แชร์/รายละเอียดรุ่นที่ทีมระบุ เทียบประกาศทีม ถ้าไม่มีเลขรุ่นในรายละเอียด **ยังตรวจรุ่นแน่นอนไม่ได้** ให้ผู้ดูแลยืนยัน ไม่ใช้วันที่อัปโหลดแทน version หรือให้ AI เดา

---

## Claude Code

### 1. Install

**วิธีนี้ทำครั้งเดียวต่อเครื่องและผู้ใช้ OS** เลือก user scope เพื่อใช้ข้ามโปรเจกต์; ไม่ได้หมายถึงลงครั้งเดียวแล้วตามบัญชีไปทุกเครื่อง

Step 1 → รับ ZIP ที่ทีมอนุมัติ แตกลงโฟลเดอร์ถาวร คัดลอก path ที่มี `.claude-plugin` และ `plugins`
Step 2 → เปิด Terminal/PowerShell แทน path ในคำสั่งแรกด้วย path จริง แล้วรัน:

```sh
claude plugin marketplace add "ABSOLUTE_PATH_TO_EXTRACTED_MARKETPLACE"
claude plugin install team-engineering-skills@team-engineering-skills-marketplace --scope user
```

Step 3 → ใน Claude Code พิมพ์ `/reload-plugins` แล้วเปิดโปรเจกต์ที่ทีมเตรียมไว้ หาก client เก่าไม่รองรับ ให้ปิดและเปิด Claude Code ใหม่ หรือขอผู้ดูแลอัปเดต client

เปลี่ยนเครื่องให้ทำซ้ำ; ต่อ Project ให้ทีมเตรียมคำสั่งเพียงครั้งเดียวตามหน้า Codex ไม่ bootstrap ซ้ำเอง [ติดตั้ง Plugins](https://code.claude.com/docs/en/discover-plugins)

### 2. Use

> ช่วยสร้าง test case จาก requirement และ UI นี้ รวมกรณีผิดพลาด โดยยังไม่ใส่ผลทดสอบจริง

ไม่ต้องเลือก Skill เองเมื่อโหลดสำเร็จ ตรวจว่าผลลัพธ์อ้างอิง Requirement ได้

### 3. Update Skill

รับชุด local รุ่นใหม่ → ปิด Claude Code → สำรองโฟลเดอร์ชุดเดิมโดยเติม `-backup` → แตกชุดใหม่ลงโฟลเดอร์สะอาดที่ **ชื่อและ path เดิม** (มี `.claude-plugin` และ `plugins` ที่ระดับเดิม) ไม่ต้องเพิ่ม marketplace ซ้ำ แล้วรันใน Terminal:

```sh
claude plugin marketplace update team-engineering-skills-marketplace
claude plugin update team-engineering-skills@team-engineering-skills-marketplace
```

ในแชตใช้ `/reload-plugins` หรือเริ่ม session ใหม่ ไม่ต้อง restart เครื่อง Local ZIP ไม่ดาวน์โหลดรุ่นใหม่เอง; Git marketplace อัปเดตได้เมื่อเปิด auto-update แต่ third-party ปิดไว้โดยปริยาย [พฤติกรรมอัปเดต](https://code.claude.com/docs/en/discover-plugins#configure-auto-updates)

### 4. Verify

ใน Terminal รัน `claude plugin list` ดู `team-engineering-skills` ว่า enabled และ version ตรงกับประกาศทีม แล้ว reload ก่อนใช้งาน รายการบนดิสก์ไม่พิสูจน์ว่า session เก่า reload แล้ว [คำสั่งตรวจรุ่น](https://code.claude.com/docs/en/plugins-reference#plugin-list)

---

รายละเอียดสำหรับผู้ดูแลเท่านั้น: [Setup / Migration](MAINTAINER_APPENDIX_TH.md) · [หลักฐานและข้อจำกัดคู่มือ](MANUAL_SOURCES_TH.md)
