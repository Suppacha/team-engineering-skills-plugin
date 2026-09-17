# Quick Start — Team Engineering Skills

สำหรับสมาชิกทีม • อ่าน Quick Start และเฉพาะ Tool ที่ใช้ประมาณ 5 นาที

> เส้นทาง native ใหม่ใช้ได้ **หลังผู้ดูแลเปิดใช้งานและผ่าน pilot** ของ client/OS นั้นเท่านั้น ขณะนี้ยังไม่รับรองว่าเปิดแล้ว หากผู้ดูแลยังไม่ประกาศ ให้ใช้ ZIP/local path รุ่นที่อนุมัติซึ่งยังเป็น fallback ที่ใช้งานได้แต่ไม่ auto-update

ชุดนี้ช่วยวิเคราะห์ Requirement, ออกแบบ UI และสร้าง Test Case ด้วย 15 Skills. ใช้เฉพาะข้อมูลที่องค์กรอนุญาตและตรวจคำตอบก่อนใช้จริง

อย่าปะปนหลักฐานห้าชนิด: **installed** คือ client ลงไว้, **loaded** คือ session ใช้อยู่, **package version** คือรุ่นปลั๊กอิน, **Skill version** คือรุ่น Skill รายตัว และ **project snapshot** ใน `.team-ai/release.json` คือคำสั่งโปรเจกต์ที่ต้อง review/update แยก. `codex --version`/`claude --version` เป็นรุ่น client

| Tool | Install | Update | Verify |
| --- | --- | --- | --- |
| [Codex](#codex) | company Workspace หลังเปิดใช้; ZIP fallback | daily provider sync แล้ว session ใหม่ | installed และ loaded แยกกัน |
| [ChatGPT](#chatgpt) | ช่องทาง cloud แบบมีเงื่อนไข | ตาม Workspace/Skill ที่ Admin ประกาศ | ตรวจรายการ/Workspace จริง |
| [Claude](#claude) | shared หรือ ZIP ราย Skill แบบมีเงื่อนไข | ตามผู้แชร์/ไฟล์ใหม่ | ตรวจ Skill details |
| [Claude Code](#claude-code) | stable marketplace ต่อเครื่อง/ผู้ใช้หลังเปิดใช้; ZIP fallback | startup auto-check แล้ว reload | list + loaded session |

ลองสั่ง: “ช่วยวิเคราะห์ requirement นี้และสร้าง test case แยกคำถามที่ยังไม่ชัด ห้ามใส่ผล PASS ก่อนรันทดสอบจริง” หาก Tool ไม่พบ Skill ให้แจ้ง ไม่ใช่อ้างว่าโหลดแล้ว

## Codex

### 1. Install

หลัง Admin ประกาศว่า company Workspace และคู่ OS/client ผ่าน pilot: เข้า Workspace บริษัท → Plugins → ติดตั้ง `team-engineering-skills` หนึ่งครั้ง → เปิด session ใหม่ ไม่เพิ่ม local marketplace ชื่อเดียวกันซ้อน บัญชีส่วนตัวและ CLI/IDE ที่ไม่ได้ pilot อยู่นอกขอบเขต

หากยังไม่เปิดใช้ ให้รับ ZIP ที่อนุมัติ แตกใน path ถาวร แล้วเพิ่ม local marketplace ตามคู่มือเดิมจากผู้ดูแล

### 2. Use

> ช่วยวิเคราะห์ requirement นี้ ออกแบบหน้าจอ และสร้าง test case ที่อ้างอิงกัน

### 3. Update Skill

native path ใช้ Workspace sync ซึ่งอาจเป็น daily ไม่ใช่ทันทีหลัง Push; รอประกาศ sync แล้วเปิด session ใหม่ ไม่ต้อง Git Pull. ZIP path ต้องรับชุดใหม่และเปลี่ยน local source ตามขั้นตอนผู้ดูแล ไม่มี auto-update

### 4. Verify

ตรวจว่า plugin แสดง Installed ใน company Workspace แล้วถาม session ใหม่ให้แสดงหลักฐาน package/Skill ที่โหลดจริง หากตรวจไม่ได้ให้รายงานว่า “ตรวจสอบไม่ได้” อย่าใช้ project snapshot หรือเลขในคู่มือนี้แทน

## ChatGPT

### 1. Install

ChatGPT cloud เป็นช่องทางแบบมีเงื่อนไขและอยู่นอก certification ของ native auto-update รอบนี้ ใช้เฉพาะเมื่อ Admin แชร์ plugin/Skill ใน Workspace ที่รองรับ: เข้า Workspace → Plugins/Skills → ติดตั้ง → เปิดแชตใหม่ GitHub public ไม่แปลว่ารายการถูกเผยแพร่แล้ว

### 2. Use

> ช่วยวิเคราะห์ requirement นี้ ถ้ายังไม่ได้โหลด Skill ของทีมให้แจ้งก่อน

### 3. Update Skill

ทำตามประกาศ Workspace/shared Skill; uploaded copy ส่วนตัวไม่ sync GitHub อัตโนมัติ

### 4. Verify

ตรวจชื่อ Workspace, รายการ Installed และรายละเอียดรุ่น ถ้าไม่มีหลักฐาน loaded version ให้ผู้ดูแลยืนยัน

## Claude

### 1. Install

Claude chat เป็นช่องทางแบบมีเงื่อนไขและอยู่นอก certification รอบนี้ ใช้ shared Skill หรือ ZIP **ราย Skill** ที่ผู้ดูแลจัดให้เท่านั้น ไม่อัปโหลด ZIP marketplace ทั้งชุด

### 2. Use

> ช่วยสร้าง test case ตามมาตรฐานทีม แยกข้อเท็จจริงกับสมมติฐาน

### 3. Update Skill

shared Skill รับการแก้จากผู้แชร์เมื่อใช้ครั้งถัดไป; uploaded copy ต้องรับไฟล์ใหม่ แล้วเปิดแชตใหม่

### 4. Verify

เปิด Skill details ตรวจผู้แชร์/รุ่น หากไม่มีเลขรุ่นอย่าเดาจากวันที่อัปโหลด

## Claude Code

### 1. Install

หลัง Admin ประกาศว่าคู่ OS/client ผ่าน pilot ให้ติดตั้ง stable marketplace หนึ่งครั้งต่อเครื่องและผู้ใช้ OS:

```sh
claude plugin marketplace add Suppacha/team-engineering-skills-plugin@stable --scope user
claude plugin install team-engineering-skills@team-engineering-skills-marketplace --scope user
```

การตั้งค่า marketplace อย่างเดียวไม่ติดตั้ง plugin และไม่ sync ตามบัญชีไปเครื่องอื่น หากยังไม่เปิดใช้ ให้คง local ZIP fallback ตามประกาศทีม

### 2. Use

> ช่วยสร้าง test case จาก requirement และ UI นี้ โดยยังไม่ใส่ผลทดสอบจริง

### 3. Update Skill

third-party auto-update ต้องเปิดสำหรับ marketplace; client ตรวจเบื้องหลังหลังเริ่มงานและอาจหน่วงได้ หลัง installed version เปลี่ยนให้ใช้ `/reload-plugins` หรือ session ใหม่ ไม่ต้องสั่ง update เองในเส้นทางที่กำลัง pilot

### 4. Verify

รัน `claude plugin list --json` ตรวจ installed source/version แล้ว `/reload-plugins` และตรวจ loaded version แยกกัน รายการบนดิสก์ไม่พิสูจน์ session เก่า

ปัญหา source ชื่อซ้ำหรือย้ายจาก ZIP ให้หยุดและติดต่อผู้ดูแล อย่าลบ backup, cache หรือไฟล์โปรเจกต์เอง รายละเอียด: [คู่มือ Admin และ migration](AUTO_UPDATE_ADMIN_TH.md) · [หลักฐาน/ข้อจำกัด](MANUAL_SOURCES_TH.md)
