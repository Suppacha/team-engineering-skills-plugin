# แบบบันทึก pilot native auto-update

> สถานะเริ่มต้นทั้งหมดคือ **NOT RUN**. เอกสารนี้ไม่ใช่ telemetry uploader และไม่ส่งข้อมูลออกอัตโนมัติ ผู้ทดสอบบันทึกเฉพาะข้อมูลสังเคราะห์/หลักฐานที่องค์กรอนุญาต ห้ามใส่ secret, prompt จริง, BA/customer material หรือข้อมูลส่วนบุคคล

ทดสอบ A → B ที่ version ต่างกันในกลุ่มจำกัด หลัง Admin configuration จริง บันทึกหลักฐาน installed และ loaded แยกกัน การมี package บนดิสก์หรือ sync report ไม่พิสูจน์ว่า session โหลดแล้ว

| Client / channel | OS | Version A | Version B | SHA/source | account scope | automatic check observation | installed evidence | loaded evidence | session/reload time | Result | limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Codex / company Workspace | macOS | — | — | — | — | — | — | — | — | NOT RUN | — |
| Codex / company Workspace | Windows | — | — | — | — | — | — | — | — | NOT RUN | — |
| Claude Code / stable Git marketplace | macOS | — | — | — | — | — | — | — | — | NOT RUN | — |
| Claude Code / stable Git marketplace | Windows | — | — | — | — | — | — | — | — | NOT RUN | — |

## วิธีบันทึกต่อแถว

1. ระบุ client version/OS จริง, Version A/B ของ package, full released SHA และ source/ref `stable`.
2. ระบุ account scope: company Workspace/member สำหรับ Codex หรือเครื่อง+ผู้ใช้ OS/user scope สำหรับ Claude Code
3. ติดตั้ง A แล้วเก็บ installed evidence; เปิด session และเก็บ loaded evidence จากแหล่งที่ตรวจย้อนกลับได้
4. เผยแพร่ B ตาม gate แล้วสังเกต automatic check: Codex ต้องมีรอบ daily sync ที่ไม่กด Sync now; Claude Code ต้องไม่สั่ง manual update และรอ startup check ตามช่วงที่บันทึก
5. บันทึกเวลารอ, เวลา session/reload, วิธี reload และ limitation; หากหลักฐานใดขาดให้คง NOT RUN หรือระบุผลล้มเหลวตามข้อเท็จจริง ห้ามเดา

หลังครบทั้งสี่แถว ให้รัน scenario ด้านล่างใน environment pilot แยกจาก production ห้ามตัด network หรือทำให้ production sync ล้มเหลวเพื่อทดสอบ เก็บหลักฐานด้วยมือในที่ที่องค์กรอนุมัติ; เอกสารนี้ไม่ใช้ credential, ไม่เรียก API และไม่ส่ง telemetry

## Scenario ก่อน wider rollout

แต่ละแถวต้องบันทึก Procedure ที่ทำจริง, Expected เทียบ Observed, Evidence reference ที่ sanitize แล้ว, limitation และ Result. ค่าเริ่มต้นทุกแถวคือ **NOT RUN**; ห้ามสร้างผลสำเร็จหรือหลักฐานแทนการทดสอบจริง

### C-MAC — Codex / company Workspace / macOS

| ID | Scenario | Procedure | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| S1 | A → B automatic | ติดตั้ง A; promote B; รอ provider daily sync โดยไม่กด Sync now; เปิด session ใหม่ | Installed และ loaded เปลี่ยนเป็น B จาก `stable` | A/B version, SHA, sync report, installed/loaded capture, เวลา | NOT RUN |
| S2 | offline/reconnect | ตัด network เฉพาะเครื่อง pilot; เปิด client; ต่อกลับแล้วรอ sync | Offline ยังใช้ A ได้ตามที่สังเกต; หลัง reconnect รับ B โดยไม่เสีย config | เวลา offline/reconnect, error, version ก่อน/หลัง | NOT RUN |
| S3 | failed sync | ใช้ isolated pilot source/config ที่ทำให้ import/sync ล้มเหลวโดยไม่กระทบ production | แสดง failure และไม่อ้างว่า B installed/loaded; รุ่นเดิมไม่ถูกลบ | isolated setup, sync error, installed/loaded capture | NOT RUN |
| S4 | stale session | ให้ sync ติดตั้ง B แต่คง session A เปิดอยู่ | Session เก่ายังไม่ถูกนับว่า loaded B; session ใหม่โหลด B | installed B, loaded A/B ก่อน/หลัง session ใหม่ | NOT RUN |
| S5 | wrong Workspace/personal account | สลับไปบัญชีส่วนตัวหรือ Workspace ที่ไม่อนุมัติ | ไม่เห็น/ไม่ใช้ plugin บริษัทและถูกจัดเป็น exclusion | account-scope label ที่ไม่เปิดเผยตัวตน, UI state | NOT RUN |
| S6 | duplicate source migration | เตรียม ZIP backup; สร้างกรณีชื่อ source ซ้ำในเครื่อง pilot; ทำ migration ตามคู่มือ | หยุดก่อน overwrite; ถอน/disable ด้วยความยินยอม; backup ยังอยู่ | inventory ก่อน/หลัง, backup hash/path ที่ sanitize | NOT RUN |
| S7 | project instruction byte equality | hash `AGENTS.md`, `CLAUDE.md`, `.team-ai` ก่อนและหลัง plugin update | byte เท่ากันทุกไฟล์; ไม่มี auto-migration | hash manifest ก่อน/หลัง | NOT RUN |
| S8 | forward recovery | จาก B ที่มี regression promote รุ่น C ที่สูงขึ้นผ่าน gate เดิม | รับ C โดยไม่ย้อน `stable` หรือเขียนทับ B | B/C version+SHA, release record, installed/loaded C | NOT RUN |

### C-WIN — Codex / company Workspace / Windows

| ID | Scenario | Procedure | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| S1 | A → B automatic | ติดตั้ง A; promote B; รอ provider daily sync โดยไม่กด Sync now; เปิด session ใหม่ | Installed และ loaded เปลี่ยนเป็น B จาก `stable` | A/B version, SHA, sync report, installed/loaded capture, เวลา | NOT RUN |
| S2 | offline/reconnect | ตัด network เฉพาะเครื่อง pilot; เปิด client; ต่อกลับแล้วรอ sync | Offline ยังใช้ A ได้ตามที่สังเกต; หลัง reconnect รับ B โดยไม่เสีย config | เวลา offline/reconnect, error, version ก่อน/หลัง | NOT RUN |
| S3 | failed sync | ใช้ isolated pilot source/config ที่ทำให้ import/sync ล้มเหลวโดยไม่กระทบ production | แสดง failure และไม่อ้างว่า B installed/loaded; รุ่นเดิมไม่ถูกลบ | isolated setup, sync error, installed/loaded capture | NOT RUN |
| S4 | stale session | ให้ sync ติดตั้ง B แต่คง session A เปิดอยู่ | Session เก่ายังไม่ถูกนับว่า loaded B; session ใหม่โหลด B | installed B, loaded A/B ก่อน/หลัง session ใหม่ | NOT RUN |
| S5 | wrong Workspace/personal account | สลับไปบัญชีส่วนตัวหรือ Workspace ที่ไม่อนุมัติ | ไม่เห็น/ไม่ใช้ plugin บริษัทและถูกจัดเป็น exclusion | account-scope label ที่ไม่เปิดเผยตัวตน, UI state | NOT RUN |
| S6 | duplicate source migration | เตรียม ZIP backup; สร้างกรณีชื่อ source ซ้ำในเครื่อง pilot; ทำ migration ตามคู่มือ | หยุดก่อน overwrite; ถอน/disable ด้วยความยินยอม; backup ยังอยู่ | inventory ก่อน/หลัง, backup hash/path ที่ sanitize | NOT RUN |
| S7 | project instruction byte equality | hash `AGENTS.md`, `CLAUDE.md`, `.team-ai` ก่อนและหลัง plugin update | byte เท่ากันทุกไฟล์; ไม่มี auto-migration | hash manifest ก่อน/หลัง | NOT RUN |
| S8 | forward recovery | จาก B ที่มี regression promote รุ่น C ที่สูงขึ้นผ่าน gate เดิม | รับ C โดยไม่ย้อน `stable` หรือเขียนทับ B | B/C version+SHA, release record, installed/loaded C | NOT RUN |

### CC-MAC — Claude Code / stable Git marketplace / macOS

| ID | Scenario | Procedure | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| S1 | A → B automatic | ติดตั้ง A/เปิด auto-update; promote B; restart และรอ background check โดยไม่สั่ง update | Installed เปลี่ยนเป็น B; หลัง `/reload-plugins` หรือ session ใหม่ loaded เป็น B | marketplace JSON, plugin list, loaded capture, เวลา | NOT RUN |
| S2 | offline/reconnect | ตัด network เฉพาะเครื่อง pilot; เปิด client; ต่อกลับและเริ่ม client ใหม่ | Offline ไม่สร้าง update สำเร็จปลอม; reconnect แล้วตรวจ B ตามช่วงที่บันทึก | network/error time, installed/loaded ก่อน/หลัง | NOT RUN |
| S3 | failed sync | ใช้ isolated pilot remote/source ที่ update ล้มเหลวโดยไม่แก้ production | รายงาน failure; A/backup ยังอยู่; ไม่อ้าง loaded B | isolated source, error, plugin list, loaded capture | NOT RUN |
| S4 | stale session | ให้ background check ติดตั้ง B โดยยังไม่ reload session A | plugin list อาจเป็น B แต่ loaded ยัง A; reload/session ใหม่จึงเป็น B | installed B และ loaded A/B แยกเวลา | NOT RUN |
| S5 | wrong Workspace/personal account | ตรวจว่า local marketplace อยู่ที่เครื่อง/user scope ไม่ตามบัญชี cloud | บัญชี/Workspace อื่นไม่ถูกนับเป็น assurance หรือ account sync | source/scope output และ account-scope note | NOT RUN |
| S6 | duplicate source migration | เก็บ ZIP backup; สร้าง marketplace ชื่อซ้ำในเครื่อง pilot; migration ตามคู่มือ | หยุดก่อน overwrite; backup/project files ไม่ถูกลบ | marketplace list ก่อน/หลัง, backup hash | NOT RUN |
| S7 | project instruction byte equality | hash `AGENTS.md`, `CLAUDE.md`, `.team-ai` ก่อน/หลัง auto-update/reload | byte เท่ากัน; update plugin ไม่แก้ project snapshot | hash manifest ก่อน/หลัง | NOT RUN |
| S8 | forward recovery | promote C ที่สูงกว่า B ผ่าน gate แล้วรอ automatic check/reload | Installed/loaded เป็น C; ไม่มี ref rollback หรือ overwrite B | B/C SHA+release, list, loaded C | NOT RUN |

### CC-WIN — Claude Code / stable Git marketplace / Windows

| ID | Scenario | Procedure | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| S1 | A → B automatic | ติดตั้ง A/เปิด auto-update; promote B; restart และรอ background check โดยไม่สั่ง update | Installed เปลี่ยนเป็น B; หลัง `/reload-plugins` หรือ session ใหม่ loaded เป็น B | marketplace JSON, plugin list, loaded capture, เวลา | NOT RUN |
| S2 | offline/reconnect | ตัด network เฉพาะเครื่อง pilot; เปิด client; ต่อกลับและเริ่ม client ใหม่ | Offline ไม่สร้าง update สำเร็จปลอม; reconnect แล้วตรวจ B ตามช่วงที่บันทึก | network/error time, installed/loaded ก่อน/หลัง | NOT RUN |
| S3 | failed sync | ใช้ isolated pilot remote/source ที่ update ล้มเหลวโดยไม่แก้ production | รายงาน failure; A/backup ยังอยู่; ไม่อ้าง loaded B | isolated source, error, plugin list, loaded capture | NOT RUN |
| S4 | stale session | ให้ background check ติดตั้ง B โดยยังไม่ reload session A | plugin list อาจเป็น B แต่ loaded ยัง A; reload/session ใหม่จึงเป็น B | installed B และ loaded A/B แยกเวลา | NOT RUN |
| S5 | wrong Workspace/personal account | ตรวจว่า local marketplace อยู่ที่เครื่อง/user scope ไม่ตามบัญชี cloud | บัญชี/Workspace อื่นไม่ถูกนับเป็น assurance หรือ account sync | source/scope output และ account-scope note | NOT RUN |
| S6 | duplicate source migration | เก็บ ZIP backup; สร้าง marketplace ชื่อซ้ำในเครื่อง pilot; migration ตามคู่มือ | หยุดก่อน overwrite; backup/project files ไม่ถูกลบ | marketplace list ก่อน/หลัง, backup hash | NOT RUN |
| S7 | project instruction byte equality | hash `AGENTS.md`, `CLAUDE.md`, `.team-ai` ก่อน/หลัง auto-update/reload | byte เท่ากัน; update plugin ไม่แก้ project snapshot | hash manifest ก่อน/หลัง | NOT RUN |
| S8 | forward recovery | promote C ที่สูงกว่า B ผ่าน gate แล้วรอ automatic check/reload | Installed/loaded เป็น C; ไม่มี ref rollback หรือ overwrite B | B/C SHA+release, list, loaded C | NOT RUN |

## Gate ก่อน wider rollout

ทั้งสี่คู่ต้องมีผลสำเร็จจริงสำหรับทุก scenario ที่ applicable พร้อม evidence/limitation; scenario ที่ใช้ไม่ได้ต้องมีเหตุผลและ **owner acceptance** แบบตรวจย้อนกลับได้ก่อนยกเว้น แถวที่ยัง NOT RUN, failure ที่ยังไม่แก้ หรือหลักฐาน installed/loaded ไม่ครบ ห้ามใช้ประกาศ Team-enabled ผลจาก OS/client หนึ่งห้ามใช้แทนอีกคู่
