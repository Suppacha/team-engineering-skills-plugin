# Quick Start — Team Engineering Skills

สำหรับสมาชิกทีม: อ่านตารางนี้แล้วข้ามไปเฉพาะ Tool ที่ใช้ สถานะ candidate 2.2.0 **ยังไม่เปิดใช้งานและ pilot ยัง NOT RUN**. เส้นทาง Codex เป็นตัวอัปเดตที่ทีมดูแล ไม่ใช่ native Codex auto-update; company Workspace พักไว้

| Tool | ติดตั้งครั้งแรก | เปลี่ยนเครื่อง | Skill Update | วิธีเช็ค Version |
| --- | --- | --- | --- | --- |
| ChatGPT | ติดตั้งจาก Personal/Shared marketplace ที่ผู้ดูแลอนุมัติ | ติดตั้งใหม่ตามบัญชี/สิทธิ์ | ตามช่องทางที่ผู้แชร์ประกาศ | ดู Installed/details แล้วเปิดแชตใหม่ |
| Codex | หลัง release + pilot ผ่าน ให้ติดตั้ง updater หนึ่งครั้งต่อผู้ใช้ OS/เครื่อง | ติดตั้ง updater ใหม่ | ทีมตรวจเมื่อ logon และทุก 4 ชั่วโมง | `status` ดู installed; เปิดแชตใหม่เพื่อพิสูจน์ loaded |
| Claude | ใช้ shared Skill หรือ ZIP ราย Skillที่ผู้ดูแลให้ | ติดตั้ง/อัปโหลดใหม่ตามบัญชี | shared Skill ตามผู้แชร์; ZIP ต้องรับใหม่ | ดู Skill details; อย่าเดาจากวันที่ |
| Claude Code | เพิ่ม stable marketplace และ plugin ต่อผู้ใช้ OS | ติดตั้งใหม่ | เปิด third-party auto-update; reload/session ใหม่ | `claude plugin list --json` + loaded evidence |

`installed` คือรุ่นบนดิสก์, `loaded` คือรุ่นที่ session ใหม่ใช้จริง, `package` คือปลั๊กอิน, `Skill` คือแต่ละทักษะ และ `project snapshot` (`AGENTS.md`, `CLAUDE.md`, `.team-ai`) ไม่ถูกแก้อัตโนมัติ

## Codex

### Install

หลังผู้ดูแลเปิด protected release, อนุมัติ release ที่แน่นอน และคู่ Codex Desktop personal/OS ผ่าน pilot แล้ว ให้ใช้ installer ที่ผู้ดูแลแจกตาม [คู่มือ personal updater](PERSONAL_AUTO_UPDATE_TH.md). ต้องมี Python 3.11+, Git และ Codex Desktop/คำสั่งภายในที่ updater ตรวจรองรับ การติดตั้งผูกกับผู้ใช้ OS และเครื่อง ไม่ sync ตามบัญชี Codex และไม่ใช้สิทธิ์ root/Admin

### Use

เปิด Codex Desktop ด้วยบัญชี Personal แล้วเปิดแชตใหม่ ตัวอย่าง: “ช่วยวิเคราะห์ requirement นี้ตามมาตรฐานทีม ถ้ายังไม่ได้โหลด Skill ให้แจ้งก่อน”

### Update Skill

หลังติดตั้ง updater แล้ว scheduler ตรวจเมื่อ logon และทุก 4 ชั่วโมง เครื่องหลับ ปิด หรือ offline อาจทำให้ช้า; จะตรวจใหม่เมื่อ session/network กลับมา updater ไม่อัปเดตตัวเองและไม่ fallback ไป `main`/feature branch

### Verify

ใช้ `status` ดู enabled/paused, installed version/SHA, last result และ reload-required แล้ว refresh/restart Codex และเปิดแชตใหม่เพื่อเก็บ loaded evidence แยกกัน คำตอบของโมเดลอย่างเดียวไม่ใช่หลักฐาน version

## ChatGPT

### Install

ใช้ Plugins Directory แท็บ Personal/Shared ตามสิทธิ์บัญชีและรายการที่ผู้ดูแลอนุมัติ แล้วเริ่มแชตใหม่ เส้นทาง company Workspace ของทีมนี้ **PAUSED** และ GitHub public ไม่ได้แปลว่า plugin ถูกเผยแพร่แล้ว

### Use

ตัวอย่าง: “ช่วยแตก acceptance criteria และระบุ assumption โดยใช้ Skill ของทีมที่โหลดอยู่”

### Update Skill

ทำตามประกาศของผู้แชร์/marketplace; uploaded copy ส่วนตัวไม่ใช่ Git auto-update ที่รับรอง

### Verify

ดู Installed และรายละเอียด source/version จาก UI แล้วเริ่มแชตใหม่ หากไม่มี loaded evidence ให้ระบุ unknown

## Claude

### Install

ใช้ shared Skill หรือ ZIP **ราย Skill** ที่ผู้ดูแลจัดให้ตามสิทธิ์บัญชี ไม่อัปโหลด ZIP marketplace ทั้งชุด

### Use

ตัวอย่าง: “ช่วยสร้าง test case ตามมาตรฐานทีม แยกข้อเท็จจริงกับสมมติฐาน”

### Update Skill

shared Skill รับการแก้จากผู้แชร์ตามบริการ; uploaded copy ต้องรับไฟล์ใหม่และเปิดแชตใหม่

### Verify

เปิด Skill details ตรวจผู้แชร์และรุ่น หากไม่มีเลขรุ่นอย่าเดาจากวันที่อัปโหลด

## Claude Code

### Install

หลัง Admin ประกาศว่าคู่ OS/client ผ่าน pilot:

```sh
claude plugin marketplace add Suppacha/team-engineering-skills-plugin@stable --scope user
claude plugin install team-engineering-skills@team-engineering-skills-marketplace --scope user
```

marketplace อย่างเดียวไม่ติดตั้ง plugin และไม่ sync ไปเครื่องอื่น

### Use

ตัวอย่าง: “ช่วยสร้าง test case จาก requirement และ UI นี้ โดยยังไม่ใส่ผลทดสอบจริง”

### Update Skill

third-party auto-update ต้องเปิดใน `/plugin` → Marketplaces; หลัง installed version เปลี่ยนให้ใช้ `/reload-plugins` หรือ session ใหม่

### Verify

ใช้ `claude plugin list --json` ตรวจ installed source/version แล้วเก็บ loaded evidence หลัง reload แยกกัน

พบ source ชื่อซ้ำ, `repair-required` หรือ migration จาก ZIP ให้หยุดและติดต่อผู้ดูแล อย่าลบ backup/cache/project files เอง: [คู่มือ Admin](AUTO_UPDATE_ADMIN_TH.md) · [ภาคผนวกซ่อม](MAINTAINER_APPENDIX_TH.md) · [หลักฐาน](MANUAL_SOURCES_TH.md)
